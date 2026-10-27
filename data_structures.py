"""Manually implemented data structures for the POS application.

No collections.deque, heapq, sortedcontainers, or third-party tree packages are used
for the required data structures.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CartNode:
    product_id: int
    name: str
    price: float
    quantity: int
    next: Optional["CartNode"] = None


class LinkedListCart:
    """Singly linked list used to manage the active shopping cart."""
    def __init__(self) -> None:
        self.head: Optional[CartNode] = None

    def add(self, product_id: int, name: str, price: float, quantity: int = 1) -> None:
        if quantity <= 0:
            raise ValueError("Quantity must be a positive whole number.")
        current = self.head
        while current:
            if current.product_id == product_id:
                current.quantity += quantity
                return
            current = current.next
        node = CartNode(product_id, name, float(price), int(quantity))
        node.next = self.head
        self.head = node

    def remove(self, product_id: int) -> bool:
        previous = None
        current = self.head
        while current:
            if current.product_id == product_id:
                if previous is None:
                    self.head = current.next
                else:
                    previous.next = current.next
                return True
            previous, current = current, current.next
        return False

    def set_quantity(self, product_id: int, quantity: int) -> bool:
        if quantity <= 0:
            return self.remove(product_id)
        current = self.head
        while current:
            if current.product_id == product_id:
                current.quantity = int(quantity)
                return True
            current = current.next
        return False

    def clear(self) -> None:
        self.head = None

    def items(self) -> list[dict[str, Any]]:
        result = []
        current = self.head
        while current:
            result.append({
                "product_id": current.product_id,
                "name": current.name,
                "price": current.price,
                "quantity": current.quantity,
                "subtotal": round(current.price * current.quantity, 2),
            })
            current = current.next
        return result

    def total(self) -> float:
        return round(sum(item["subtotal"] for item in self.items()), 2)

    def __len__(self) -> int:
        count = 0
        current = self.head
        while current:
            count += 1
            current = current.next
        return count


@dataclass
class AVLNode:
    key: str
    value: dict[str, Any]
    left: Optional["AVLNode"] = None
    right: Optional["AVLNode"] = None
    height: int = 1


class AVLTree:
    """AVL tree keyed by normalized product name, supporting insert/search/delete."""
    def __init__(self) -> None:
        self.root: Optional[AVLNode] = None

    @staticmethod
    def _height(node: Optional[AVLNode]) -> int:
        return node.height if node else 0

    @classmethod
    def _update_height(cls, node: AVLNode) -> None:
        node.height = 1 + max(cls._height(node.left), cls._height(node.right))

    @classmethod
    def _balance(cls, node: Optional[AVLNode]) -> int:
        return cls._height(node.left) - cls._height(node.right) if node else 0

    @staticmethod
    def _rotate_right(y: AVLNode) -> AVLNode:
        x = y.left
        assert x is not None
        subtree = x.right
        x.right = y
        y.left = subtree
        AVLTree._update_height(y)
        AVLTree._update_height(x)
        return x

    @staticmethod
    def _rotate_left(x: AVLNode) -> AVLNode:
        y = x.right
        assert y is not None
        subtree = y.left
        y.left = x
        x.right = subtree
        AVLTree._update_height(x)
        AVLTree._update_height(y)
        return y

    @classmethod
    def _rebalance(cls, node: AVLNode) -> AVLNode:
        cls._update_height(node)
        balance = cls._balance(node)
        if balance > 1:
            if cls._balance(node.left) < 0:
                assert node.left is not None
                node.left = cls._rotate_left(node.left)
            return cls._rotate_right(node)
        if balance < -1:
            if cls._balance(node.right) > 0:
                assert node.right is not None
                node.right = cls._rotate_right(node.right)
            return cls._rotate_left(node)
        return node

    def insert(self, key: str, value: dict[str, Any]) -> None:
        normalized = key.strip().casefold()
        if not normalized:
            raise ValueError("AVL Tree keys cannot be empty.")
        self.root = self._insert(self.root, normalized, value)

    @classmethod
    def _insert(cls, node: Optional[AVLNode], key: str, value: dict[str, Any]) -> AVLNode:
        if node is None:
            return AVLNode(key, value)
        if key < node.key:
            node.left = cls._insert(node.left, key, value)
        elif key > node.key:
            node.right = cls._insert(node.right, key, value)
        else:
            node.value = value
            return node
        return cls._rebalance(node)

    def search(self, key: str) -> Optional[dict[str, Any]]:
        normalized = key.strip().casefold()
        current = self.root
        while current:
            if normalized == current.key:
                return current.value
            current = current.left if normalized < current.key else current.right
        return None

    def delete(self, key: str) -> bool:
        normalized = key.strip().casefold()
        self.root, deleted = self._delete(self.root, normalized)
        return deleted

    @classmethod
    def _minimum(cls, node: AVLNode) -> AVLNode:
        while node.left:
            node = node.left
        return node

    @classmethod
    def _delete(cls, node: Optional[AVLNode], key: str) -> tuple[Optional[AVLNode], bool]:
        if node is None:
            return None, False
        deleted = False
        if key < node.key:
            node.left, deleted = cls._delete(node.left, key)
        elif key > node.key:
            node.right, deleted = cls._delete(node.right, key)
        else:
            deleted = True
            if node.left is None:
                return node.right, True
            if node.right is None:
                return node.left, True
            successor = cls._minimum(node.right)
            node.key, node.value = successor.key, successor.value
            node.right, _ = cls._delete(node.right, successor.key)
        return (cls._rebalance(node), deleted) if node else (None, deleted)

    def inorder(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        def walk(node: Optional[AVLNode]) -> None:
            if node:
                walk(node.left)
                result.append(node.value)
                walk(node.right)
        walk(self.root)
        return result


@dataclass
class HeapEntry:
    priority: int
    order_id: int
    created_at: str
    customer_name: str
    total: float
    status: str = "Pending"


class MinHeap:
    """Binary min-heap: lowest priority number is served first."""
    def __init__(self) -> None:
        self._data: list[HeapEntry] = []

    @staticmethod
    def _key(entry: HeapEntry) -> tuple[int, str, int]:
        return (entry.priority, entry.created_at, entry.order_id)

    def push(self, entry: HeapEntry) -> None:
        self._data.append(entry)
        index = len(self._data) - 1
        while index > 0:
            parent = (index - 1) // 2
            if self._key(self._data[parent]) <= self._key(self._data[index]):
                break
            self._data[parent], self._data[index] = self._data[index], self._data[parent]
            index = parent

    def peek(self) -> Optional[HeapEntry]:
        return self._data[0] if self._data else None

    def pop(self) -> Optional[HeapEntry]:
        if not self._data:
            return None
        if len(self._data) == 1:
            return self._data.pop()
        minimum = self._data[0]
        self._data[0] = self._data.pop()
        index = 0
        size = len(self._data)
        while True:
            left = 2 * index + 1
            right = left + 1
            smallest = index
            if left < size and self._key(self._data[left]) < self._key(self._data[smallest]):
                smallest = left
            if right < size and self._key(self._data[right]) < self._key(self._data[smallest]):
                smallest = right
            if smallest == index:
                break
            self._data[index], self._data[smallest] = self._data[smallest], self._data[index]
            index = smallest
        return minimum

    def ordered_items(self) -> list[HeapEntry]:
        """Return a sorted view without mutating the live heap."""
        copy = MinHeap()
        for entry in self._data:
            copy.push(entry)
        result = []
        while copy:
            result.append(copy.pop())
        return result

    def __len__(self) -> int:
        return len(self._data)

    def __bool__(self) -> bool:
        return bool(self._data)
