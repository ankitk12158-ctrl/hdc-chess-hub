import numpy as np

DIMENSIONS = 10000

def generate_hypervector():
    return np.random.choice([-1, 1], size=DIMENSIONS)

class HDCChessEncoder:
    def __init__(self):
        self.squares = {f"{chr(file)}{rank}": generate_hypervector() for file in range(97, 105) for rank in range(1, 9)}
        pieces = ['wp', 'wn', 'wb', 'wr', 'wq', 'wk', 'bp', 'bn', 'bb', 'br', 'bq', 'bk'] 
        self.pieces = {piece: generate_hypervector() for piece in pieces}

    def bind(self, piece_vec, square_vec):
        return np.multiply(piece_vec, square_vec)

    def bundle(self, bound_vectors):
        if not bound_vectors:
            return np.ones(DIMENSIONS)
        summed_vec = np.sum(bound_vectors, axis=0)
        return np.where(summed_vec >= 0, 1, -1)

    def cosine_similarity(self, vec_a, vec_b):
        return np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b))