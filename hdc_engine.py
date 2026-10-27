import chess
import numpy as np
from hdc_encoder import HDCChessEncoder

class HDCEngine:
    def __init__(self):
        self.encoder = HDCChessEncoder()

    def board_to_vector(self, board):
        bound_vectors = []
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                sq_name = chess.square_name(square)
                color = 'w' if piece.color == chess.WHITE else 'b'
                p_type = piece.symbol().lower()
                v_piece = self.encoder.pieces[f"{color}{p_type}"]
                v_square = self.encoder.squares[sq_name]
                bound_vectors.append(self.encoder.bind(v_piece, v_square))
        if not bound_vectors:
            return np.ones(10000)
        return self.encoder.bundle(bound_vectors)

    def evaluate_board(self, board):
        piece_values = { chess.PAWN: 10, chess.KNIGHT: 30, chess.BISHOP: 30, chess.ROOK: 50, chess.QUEEN: 90, chess.KING: 900 }
        score = 0
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                val = piece_values.get(piece.piece_type, 0)
                if piece.color == chess.BLACK:
                    score += val
                else:
                    score -= val
        return score

    def minimax(self, board, depth, alpha, beta, is_maximizing):
        if depth == 0 or board.is_game_over():
            return self.evaluate_board(board)
        
        if is_maximizing:
            max_eval = -99999
            for move in board.legal_moves:
                board.push(move)
                eval = self.minimax(board, depth - 1, alpha, beta, False)
                board.pop()
                max_eval = max(max_eval, eval)
                alpha = max(alpha, eval)
                if beta <= alpha: break
            return max_eval
        else:
            min_eval = 99999
            for move in board.legal_moves:
                board.push(move)
                eval = self.minimax(board, depth - 1, alpha, beta, True)
                board.pop()
                min_eval = min(min_eval, eval)
                beta = min(beta, eval)
                if beta <= alpha: break
            return min_eval

    def find_target_state_move(self, board, player_elo):
        # AI Logic: ELO ke hisaab se difficulty badhegi
        if player_elo < 500: depth = 1
        elif player_elo < 1000: depth = 2
        elif player_elo < 1500: depth = 3
        else: depth = 4 # 1500+ pe Invincible mode
        
        best_move = None
        best_score = -99999
        for move in board.legal_moves:
            board.push(move)
            score = self.minimax(board, depth, -99999, 99999, False)
            board.pop()
            if score > best_score:
                best_score = score
                best_move = move
        return best_move

    def choose_move(self, board, player_elo=0):
        ideal_move = self.find_target_state_move(board, player_elo)
        if not ideal_move:
            return list(board.legal_moves)[0]
            
        board.push(ideal_move)
        target_win_vector = self.board_to_vector(board)
        board.pop()

        best_move = None
        highest_similarity = -2.0
        
        for move in board.legal_moves:
            board.push(move)
            future_vector = self.board_to_vector(board)
            similarity = self.encoder.cosine_similarity(future_vector, target_win_vector)
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_move = move
            board.pop()
            
        return best_move