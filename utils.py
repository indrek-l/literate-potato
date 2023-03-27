from datetime import datetime
from time import time
from random import choice

def pretty_board(board):
    for i, pair in enumerate(board):
        board[i] = (' ', pair[1]) if pair[0] == '_' else pair
    return f"""
+---+---+---+   1 - {board[0][1]}
| {board[0][0]} | {board[1][0]} | {board[2][0]} |   2 - {board[1][1]}
+---+---+---+   3 - {board[2][1]}
| {board[3][0]} | {board[4][0]} | {board[5][0]} |   4 - {board[3][1]}
+---+---+---+   5 - {board[4][1]}
| {board[6][0]} | {board[7][0]} | {board[8][0]} |   6 - {board[5][1]}
+---+---+---+   7 - {board[6][1]}
                8 - {board[7][1]}
                9 - {board[8][1]}
"""

board = [[choice(['X', 'O', '_']), datetime.fromtimestamp(time()).strftime('%H:%M:%S')] for _ in range(9)]

print(pretty_board(board))