import hashlib
import json
from time import time

class Blockchain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        # Create the Genesis Block
        self.create_block(previous_hash='1', proof=100)

    def create_block(self, proof, previous_hash=None):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.pending_transactions,
            'proof': proof,
            'previous_hash': previous_hash or (self.hash(self.chain[-1]) if self.chain else '0'),
        }
        block['hash'] = self.hash(block)
        self.pending_transactions = []
        self.chain.append(block)
        return block

    def add_block(self, data):
        """Standard method for adding any data (Inscription or Judicial Verdict) to the chain."""
        self.pending_transactions = [data]
        return self.create_block(proof=123)

    @staticmethod
    def hash(block):
        # Ensure consistent hashing by ignoring the hash key itself
        block_copy = {k: v for k, v in block.items() if k != 'hash'}
        block_string = json.dumps(block_copy, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def get_block_by_hash(self, block_hash):
        return next((b for b in self.chain if b['hash'] == block_hash), None)