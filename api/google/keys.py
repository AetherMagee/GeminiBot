import asyncio
import os
import random
from collections import defaultdict

from loguru import logger


class OutOfKeysException(Exception):
    pass

class OutOfBillingKeysException(Exception):
    pass


class ApiKeyManager:
    def __init__(self, keys_file_path, resource_exhausted_threshold=3):
        self.keys_file_path = keys_file_path
        self.resource_exhausted_threshold = resource_exhausted_threshold

        self.api_keys = []
        self.billing_api_keys = []

        self.active_api_keys = []
        self.active_billing_api_keys = []

        self.api_key_index = 0
        self.billing_api_key_index = 0

        self.api_keys_error_counts = defaultdict(int)
        self.billing_api_keys_error_counts = defaultdict(int)
        self.resource_exhausted_error_counts = defaultdict(int)
        self.billing_resource_exhausted_error_counts = defaultdict(int)

        self.keys_lock = asyncio.Lock()

        self._load_keys()

    async def get_api_key(self, billing_only=False):
        async with self.keys_lock:
            keys, index, error_counts = self._select_key_set(billing_only)

            if not keys:
                if billing_only:
                    raise OutOfBillingKeysException("No active billing API keys available")
                else:
                    raise OutOfKeysException("No active API keys available")

            key = keys[index % len(keys)]
            self._increment_index(billing_only)

            if index % 50 == 0 and index > 0:
                logger.debug(f"{'Billing ' if billing_only else ''}Error counts: {dict(error_counts)}")

            return key

    async def handle_key_error(self, key, error_status, is_billing=False, bot=None):
        async with self.keys_lock:
            if error_status == "RESOURCE_EXHAUSTED":
                self._handle_resource_exhausted_error(key, is_billing, bot)
            else:
                error_counts = self.billing_api_keys_error_counts if is_billing else self.api_keys_error_counts
                error_counts[key] += 1

    async def _notify_admin(self, key, bot):
        target_id = int(os.getenv("FEEDBACK_TARGET_ID"))
        if not target_id:
            return
        try:
            await bot.send_message(
                target_id,
                f"⚠️ <b>Ключ <code>{key[-6:]}</code> удалён из циркуляции.</b> (осталось {len(self.active_api_keys)} ключей)",
            )
        except Exception as e:
            logger.error(f"Failed to send key removal notification: {e}")

    def _load_keys(self):
        if not os.path.exists(self.keys_file_path):
            logger.exception(
                f"Couldn't find the key list file in the configured data folder. "
                f"Please make sure that {self.keys_file_path} exists."
            )
            exit(1)

        with open(self.keys_file_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("AIzaSy"):
                    key_parts = line.split(" ", maxsplit=1)
                    key = key_parts[0]
                    self.api_keys.append(key)
                    if len(key_parts) > 1 and key_parts[1].lower() in ["b", "| billing enabled"]:
                        self.billing_api_keys.append(key)

        random.shuffle(self.api_keys)
        random.shuffle(self.billing_api_keys)

        logger.info(
            f"Loaded {len(self.api_keys)} API keys, "
            f"{len(self.billing_api_keys)} of them marked as billing-enabled."
        )

        self.active_api_keys = self.api_keys.copy()
        self.active_billing_api_keys = self.billing_api_keys.copy()

    def _select_key_set(self, billing_only):
        if billing_only:
            return self.active_billing_api_keys, self.billing_api_key_index, self.billing_api_keys_error_counts
        return self.active_api_keys, self.api_key_index, self.api_keys_error_counts

    def _increment_index(self, billing_only):
        if billing_only:
            self.billing_api_key_index += 1
        else:
            self.api_key_index += 1

    def _handle_resource_exhausted_error(self, key, is_billing, bot):
        error_counts, active_keys = self._select_error_set(is_billing)
        error_counts[key] += 1

        if error_counts[key] >= self.resource_exhausted_threshold:
            if key in active_keys:
                active_keys.remove(key)
            logger.warning(
                f"Key {key} has reached RESOURCE_EXHAUSTED error threshold and is removed from active keys."
            )
            if bot:
                asyncio.create_task(self._notify_admin(key, bot))

    def _select_error_set(self, is_billing):
        if is_billing:
            return self.billing_resource_exhausted_error_counts, self.active_billing_api_keys
        return self.resource_exhausted_error_counts, self.active_api_keys

    def get_active_keys(self, billing_only=False):
        return self.active_billing_api_keys if billing_only else self.active_api_keys
