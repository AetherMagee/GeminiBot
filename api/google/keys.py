import asyncio
import os
import random
from collections import defaultdict

from loguru import logger


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
                if line.startswith("AIza"):
                    key_parts = line.split(" ")
                    key = key_parts[0]
                    self.api_keys.append(key)
                    if len(key_parts) > 1 and key_parts[1].lower() == "b":
                        self.billing_api_keys.append(key)

        random.shuffle(self.api_keys)
        random.shuffle(self.billing_api_keys)

        logger.info(
            f"Loaded {len(self.api_keys)} API keys, "
            f"{len(self.billing_api_keys)} of them marked as billing-enabled."
        )

        self.active_api_keys = self.api_keys.copy()
        self.active_billing_api_keys = self.billing_api_keys.copy()

    async def get_api_key(self, billing_only=False):
        async with self.keys_lock:
            if billing_only:
                if not self.active_billing_api_keys:
                    raise Exception("No active billing API keys available")
                key = self.active_billing_api_keys[
                    self.billing_api_key_index % len(self.active_billing_api_keys)
                    ]
                self.billing_api_key_index += 1
                if self.billing_api_key_index % 50 == 0:
                    logger.debug(
                        f"Billing error counts: {dict(self.billing_api_keys_error_counts)}"
                    )
                return key
            else:
                if not self.active_api_keys:
                    raise Exception("No active API keys available")
                key = self.active_api_keys[
                    self.api_key_index % len(self.active_api_keys)
                    ]
                self.api_key_index += 1
                if self.api_key_index % 50 == 0:
                    logger.debug(f"Error counts: {dict(self.api_keys_error_counts)}")
                return key

    async def handle_key_error(self, key, error_status, is_billing=False, admin_ids=None, bot=None):
        async with self.keys_lock:
            if error_status == "RESOURCE_EXHAUSTED":
                if is_billing:
                    error_counts = self.billing_resource_exhausted_error_counts
                    active_keys = self.active_billing_api_keys
                else:
                    error_counts = self.resource_exhausted_error_counts
                    active_keys = self.active_api_keys

                error_counts[key] += 1

                if error_counts[key] >= self.resource_exhausted_threshold:
                    if key in active_keys:
                        active_keys.remove(key)
                    logger.warning(
                        f"Key {key} has reached RESOURCE_EXHAUSTED error threshold and is removed from active keys."
                    )
                    # Optionally, send a notification to admins
                    if admin_ids and bot:
                        try:
                            await bot.send_message(
                                admin_ids[0],
                                f"⚠️ <b>Ключ <code>{key[-6:]}</code> удалён из циркуляции.</b>",
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to send message to admin {admin_ids[0]}: {e}"
                            )
            else:
                if is_billing:
                    error_counts = self.billing_api_keys_error_counts
                else:
                    error_counts = self.api_keys_error_counts

                error_counts[key] += 1

    def get_all_keys(self, billing_only=False):
        return self.billing_api_keys if billing_only else self.api_keys

    def get_active_keys(self, billing_only=False):
        return self.active_billing_api_keys if billing_only else self.active_api_keys
