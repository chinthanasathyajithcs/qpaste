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

if __name__ == "__main__":
    unittest.main()
