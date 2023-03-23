from concurrent import futures
import grpc
import datetime
import itertools
import sys
import time

import tictactoe_pb2
import tictactoe_pb2_grpc

from utility import pass_election_message

# Pordid peaksid vist olema saladused seal saladuste hoidlas, mille eest lisapunkte saab
MAX_PID = 2
PORTS = {}
for i in range(MAX_PID + 1):
    PORTS[i] = 20040 + i


class TicTacToeServicer(tictactoe_pb2_grpc.TicTacToeServicer):
    def __init__(self, pid):
        self.clock = 0
        self.pid = pid
    
    def start_game(self, request, context):
        pass

    def set_symbol(self, request, context):
        pass
    
    def list_board(self, request, context):
        pass
    
    def set_node_time(self, request, context):
        pass
    
    def check_winner(self, request, context):
        pass
    
    def check_timeout(self, request, context):
        pass
    

class TicTacToeServer:
    def __init__(self, pid) -> None:
        self.pid = pid


class TicTacToeClient:
    def __init__(self) -> None:
        pass

def main():
    pass

if __name__ == "__main__":
    main()
