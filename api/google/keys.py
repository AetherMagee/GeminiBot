import asyncio
import os
import time
from collections import defaultdict

from loguru import logger

from main import bot


class OutOfKeysException(Exception):
    pass


class OutOfBillingKeysException(Exception):
    pass


class ApiKeyManager:
    def __init__(self, keys_file_path, exhaust_bantime=18 * 3600):
        self.keys_file_path = keys_file_path
        self.exhausted_key_lifetime = exhaust_bantime  # in seconds

        self.api_keys = []
        self.billing_api_keys = []

        self.active_api_keys = []
        self.active_billing_api_keys = []

        self.exhausted_api_keys = {}  # key: timestamp when exhausted
        self.exhausted_billing_api_keys = {}

        self.api_key_index = 0
        self.billing_api_key_index = 0

        self.api_keys_error_counts = defaultdict(int)
        self.billing_api_keys_error_counts = defaultdict(int)

        self.keys_lock = asyncio.Lock()

        self._load_keys()

    async def get_api_key(self, billing_only=False):
        async with self.keys_lock:
            # Reactivate exhausted keys if their cooldown has expired
            self._reactivate_exhausted_keys(billing_only)

            keys, index, error_counts = self._select_key_set(billing_only)

            if not keys:
                if billing_only:
                    raise OutOfBillingKeysException("No active billing API keys available")
                else:
                    raise OutOfKeysException("No active API keys available")

            key = keys[index % len(keys)]
            self._increment_index(billing_only)

            return key

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
                    if key in self.api_keys:
                        logger.warning(f"Key {key[-6:]} has duplicates in the list file.")
                        continue
                    self.api_keys.append(key)
                    if len(key_parts) > 1 and key_parts[1].lower() in ["b", "| billing enabled"]:
                        self.billing_api_keys.append(key)

        # Initialize active keys
        self.active_api_keys = self.api_keys.copy()
        self.active_billing_api_keys = self.billing_api_keys.copy()

        logger.info(
            f"Loaded {len(self.api_keys)} API keys, "
            f"{len(self.billing_api_keys)} of them marked as billing-enabled."
        )

    def _select_key_set(self, billing_only):
        if billing_only:
            keys = [k for k in self.active_billing_api_keys if k not in self.exhausted_billing_api_keys]
            return keys, self.billing_api_key_index, self.billing_api_keys_error_counts
        else:
            keys = [k for k in self.active_api_keys if k not in self.exhausted_api_keys]
            return keys, self.api_key_index, self.api_keys_error_counts

    def _increment_index(self, billing_only):
        if billing_only:
            self.billing_api_key_index += 1
        else:
            self.api_key_index += 1

    def timeout_key(self, key, is_billing):
        now = time.time()
        if is_billing:
            if key in self.active_billing_api_keys:
                self.active_billing_api_keys.remove(key)
            self.exhausted_billing_api_keys[key] = now
            logger.info(f"Billing API key {key[-6:]} exhausted and moved to exhausted list.")
        else:
            if key in self.active_api_keys:
                self.active_api_keys.remove(key)
            self.exhausted_api_keys[key] = now
            logger.info(f"API key {key[-6:]} exhausted and moved to exhausted list.")

    def remove_key_permanently(self, key, is_billing):
        if is_billing:
            self.active_billing_api_keys = [k for k in self.active_billing_api_keys if k != key]
            self.exhausted_billing_api_keys.pop(key, None)
            logger.warning(f"Billing API key {key[-6:]} removed permanently due to invalidity.")
        else:
            self.active_api_keys = [k for k in self.active_api_keys if k != key]
            self.exhausted_api_keys.pop(key, None)
            logger.warning(f"API key {key[-6:]} removed permanently due to invalidity.")

        asyncio.create_task(self._notify_admin(key, bot, "Invalid API key"))

    async def _notify_admin(self, key, bot, reason=''):
        target_id = int(os.getenv("FEEDBACK_TARGET_ID"))
        if not target_id:
            return
        try:
            await bot.send_message(
                target_id,
                f"⚠️ <b>Ключ <code>{key[-6:]}</code> удалён из ротации:</b> {reason}",
            )
        except Exception as e:
            logger.error(f"Failed to send key removal notification: {e}")

    def _reactivate_exhausted_keys(self, is_billing):
        now = time.time()
        if is_billing:
            exhausted_keys = self.exhausted_billing_api_keys
            active_keys = self.active_billing_api_keys
        else:
            exhausted_keys = self.exhausted_api_keys
            active_keys = self.active_api_keys

        keys_to_reactivate = []
        for key, timestamp in exhausted_keys.items():
            if now - timestamp >= self.exhausted_key_lifetime:
                keys_to_reactivate.append(key)

        for key in keys_to_reactivate:
            exhausted_keys.pop(key)
            active_keys.append(key)
            logger.info(f"Key {key[-6:]} reactivated after cooldown.")

    def get_key_statuses(self):
        statuses = {
            'active': {
                'api_keys': len(self.active_api_keys),
                'billing_api_keys': len(self.active_billing_api_keys)
            },
            'exhausted': {
                'api_keys': len(self.exhausted_api_keys),
                'billing_api_keys': len(self.exhausted_billing_api_keys)
            },
            'total': {
                'api_keys': len(self.api_keys),
                'billing_api_keys': len(self.billing_api_keys)
            }
        }
        return statuses
