import unittest
from core.clipboard_queue import ClipboardQueue
from ui.inspector import QueueInspectorWindow


class TestQueueInspector(unittest.TestCase):
    def setUp(self):
        self.queue = ClipboardQueue()
        self.queue.push("Snippet 1")
        self.queue.push("Snippet 2")
        self.queue.push("Snippet 3")
        self.inspector = QueueInspectorWindow(self.queue)

    def test_queue_manipulation_methods(self):
        # Initial count
        self.assertEqual(len(self.queue), 3)

        # Test move_up (move index 1 to 0)
        self.queue.move_item(1, 0)
        items = self.queue.get_items()
        self.assertEqual(items[0], "Snippet 2")
        self.assertEqual(items[1], "Snippet 1")

        # Test move_down (move index 0 to 1)
        self.queue.move_item(0, 1)
        items = self.queue.get_items()
        self.assertEqual(items[0], "Snippet 1")
        self.assertEqual(items[1], "Snippet 2")

        # Test delete
        self.queue.remove_at(1)
        items = self.queue.get_items()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0], "Snippet 1")
        self.assertEqual(items[1], "Snippet 3")

        # Test clear
        self.queue.clear()
        self.assertEqual(len(self.queue), 0)

    # --- TDD Slices for GUI Polish & Feature Enhancements ---

    def test_get_item_by_index(self):
        """Verify get_item returns the exact unformatted string at index."""
        self.assertEqual(self.queue.get_item(0), "Snippet 1")
        self.assertEqual(self.queue.get_item(2), "Snippet 3")
        self.assertIsNone(self.queue.get_item(99))

    def test_promote_to_front(self):
        """Verify promote_to_front moves item at index directly to index 0 (next to paste)."""
        # Initial: ["Snippet 1", "Snippet 2", "Snippet 3"]
        result = self.queue.promote_to_front(2)  # Promote "Snippet 3"
        self.assertTrue(result)

        items = self.queue.get_items()
        self.assertEqual(items[0], "Snippet 3")
        self.assertEqual(items[1], "Snippet 1")
        self.assertEqual(items[2], "Snippet 2")

    def test_promote_invalid_index(self):
        """Verify promote_to_front handles out of bounds indices safely."""
        self.assertFalse(self.queue.promote_to_front(-1))
        self.assertFalse(self.queue.promote_to_front(10))


if __name__ == "__main__":
    unittest.main()
