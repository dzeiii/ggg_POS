import unittest
from data_structures import LinkedListCart, AVLTree, MinHeap, HeapEntry


class TestLinkedListCart(unittest.TestCase):
    def test_add_merge_update_remove(self):
        cart = LinkedListCart()
        cart.add(1, "Coffee", 50, 1)
        cart.add(1, "Coffee", 50, 2)
        cart.add(2, "Tea", 30, 1)
        self.assertEqual(len(cart), 2)
        self.assertEqual(cart.total(), 180.0)
        self.assertTrue(cart.set_quantity(1, 4))
        self.assertEqual(cart.total(), 230.0)
        self.assertTrue(cart.remove(2))
        self.assertEqual(len(cart), 1)
        cart.clear()
        self.assertEqual(len(cart), 0)

    def test_invalid_quantity(self):
        with self.assertRaises(ValueError):
            LinkedListCart().add(1, "Coffee", 50, 0)


class TestAVLTree(unittest.TestCase):
    def test_insert_search_delete_and_order(self):
        tree = AVLTree()
        for name in ["Mango", "Apple", "Pear", "Banana", "Orange", "Grape"]:
            tree.insert(name, {"name": name})
        self.assertEqual(tree.search("apple")["name"], "Apple")
        self.assertIsNone(tree.search("missing"))
        self.assertTrue(tree.delete("Mango"))
        self.assertIsNone(tree.search("Mango"))
        names = [item["name"].casefold() for item in tree.inorder()]
        self.assertEqual(names, sorted(names))
        self.assertFalse(tree.delete("not here"))


class TestMinHeap(unittest.TestCase):
    def test_priority_order(self):
        heap = MinHeap()
        heap.push(HeapEntry(4, 1, "2026-01-01T10:00:00", "A", 10))
        heap.push(HeapEntry(1, 2, "2026-01-01T10:02:00", "B", 20))
        heap.push(HeapEntry(1, 3, "2026-01-01T10:01:00", "C", 30))
        self.assertEqual(heap.pop().order_id, 3)
        self.assertEqual(heap.pop().order_id, 2)
        self.assertEqual(heap.pop().order_id, 1)
        self.assertIsNone(heap.pop())


if __name__ == "__main__":
    unittest.main(verbosity=2)
