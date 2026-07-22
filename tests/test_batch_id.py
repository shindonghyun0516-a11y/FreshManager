from __future__ import annotations

import unittest

from freshmanager.batch_id import BatchIdValidationError, canonical_batch_id


CANONICAL_BATCH_ID = "11111111-1111-4111-8111-111111111111"
LETTERED_BATCH_ID = "abcdefab-cdef-4abc-8def-abcdefabcdef"


class BatchIdTests(unittest.TestCase):
    def test_canonical_batch_id_is_returned_unchanged(self) -> None:
        result = canonical_batch_id(CANONICAL_BATCH_ID)
        self.assertEqual(result, CANONICAL_BATCH_ID)
        self.assertIs(result, CANONICAL_BATCH_ID)

    def test_noncanonical_or_path_like_values_are_rejected(self) -> None:
        invalid_values = (
            "",
            "   ",
            f" {CANONICAL_BATCH_ID}",
            f"{CANONICAL_BATCH_ID} ",
            LETTERED_BATCH_ID.upper(),
            "/tmp/11111111-1111-4111-8111-111111111111",
            "../11111111-1111-4111-8111-111111111111",
            "11111111/1111-4111-8111-111111111111",
            "11111111\\1111-4111-8111-111111111111",
            "not-a-batch-id",
            "11111111-1111-6111-8111-111111111111",
            "11111111-1111-4111-7111-111111111111",
        )
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(BatchIdValidationError):
                canonical_batch_id(value)


if __name__ == "__main__":
    unittest.main()
