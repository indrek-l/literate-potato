import random
import sys
import grpc
import threading
from concurrent import futures
from datetime import datetime, timedelta
from time import time, sleep
from itertools import combinations

import tictactoe_pb2
import tictactoe_pb2_grpc


# Pordid peaksid vist olema saladused seal saladuste hoidlas, mille eest lisapunkte saab
MAX_PID = 2
PORTS = [20040 + i for i in range(MAX_PID + 1)]
PID = int(sys.argv[1])
TIME_DIFF = -1
LEADER_PID = -1

class TicTacToeServicer(tictactoe_pb2_grpc.TicTacToeServicer):
    def __init__(self):
        self.board = None
        self.nodes = None
        self.symbols = None
        self.moving = -1

    def set_symbol(self, request, context):
        if self.moving == request.sender_node:
            if self.symbols[self.moving] == request.symbol:
                if self.board[request.position-1] == "_":
                    self.board[request.position-1] = (request.symbol, datetime.fromtimestamp(request.timestamp).strftime('%H:%M:%S'))
                    
                    check_winner()

                    return tictactoe_pb2.SetSymbolResponse(success=True, message=f"Move successful. Symbol {request.symbol} set at position {request.position}")
                
                return tictactoe_pb2.SetSymbolResponse(success=False, message=f"Position {request.position} is taken. Try again")
            
            return tictactoe_pb2.SetSymbolResponse(success=False, message=f"Your symbol is {self.symbols[request.sender_node]} and not {request.symbol}. Try again.")

        return tictactoe_pb2.SetSymbolResponse(success=False, message=f"It is not your turn. Node-{self.nodes[self.moving]} moves next")

    def check_winner(self):
        winner = None
        for i in range(3):
            if '_' != self.board[0 + i*3][0] == self.board[1 + i*3][0] == self.board[2 + i*3][0]:
                winner = self.board[0 + i*3][0]
            if '_' != self.board[0 + i][0] == self.board[3 + i][0] == self.board[6 + i][0]:
                winner = self.board[0 + i][0]
        if '_' != self.board[0][0] == self.board[4][0] == self.board[8][0]:
            winner = self.board[0][0]
        if '_' != self.board[2][0] == self.board[4][0] == self.board[6][0]:
            winner = self.board[2][0]
        if not winner and '_' not in self.board:
            pass

        tictactoe_pb2.AnnounceWinnerRequest(winner=self.symbols.index(winner))
            
    def announce_winner(self, request, context):
        pass

    def list_board(self, request, context):
        print_board = [f"{sym}:<{ts}>" for sym, ts in self.board]
        return tictactoe_pb2.ListBoardResponse(board=print_board)
    
    def check_timeout(self, request, context):  
        pass
    
    def get_node_time(self, request, context):
        return tictactoe_pb2.GetNodeTimeResponse(timestamp=time())
    
    def set_node_time(self, request, context):
        if request.requester_pid == LEADER_PID or LEADER_PID == -1: # :unamused:
            TIME_DIFF = request.timestamp - time()
            return tictactoe_pb2.SetNodeTimeResponse(message=f"Node-{PID} new clock {datetime.fromtimestamp(request.timestamp).strftime('%H:%M:%S')}")
        return tictactoe_pb2.SetNodeTimeResponse(message = f"Only the game master (Node-{LEADER_PID}) can modify the clock of Node-{PID}")

    def election(self, request, context):
        initiator = request.candidate_pids[0]
        if initiator == PID:

            if request.leader_pid == -1:
                highest_pid = max(request.candidate_pids)
        
                if highest_pid == PID:
                    # Initiator is the leader. No need to check if the leader is still working.
                    return tictactoe_pb2.ElectionResponse(leader_pid=PID)
                leader_message = tictactoe_pb2.ElectionRequest(leader_pid=highest_pid, candidate_pids=[PID])
                return send_election_message(leader_message)
        
            if request.leader_pid in request.candidate_pids:
                return tictactoe_pb2.ElectionResponse(leader_pid=request.leader_pid)
        
            print("Election unsuccesful. Restarting.")
            return self.election(tictactoe_pb2.ElectionRequest(leader_pid=-1, candidate_pids=[PID]))
        
        # Current node did not initiate election. Pass the message on.
        request.candidate_pids.append(PID)
        response = send_election_message(request)
        LEADER_PID = response.leader_pid  # Other processes learn who the leader is.
        return response

    def init_leader(self, request, context):
        self.board = [ "_" for i in range[9] ]
        self.nodes = [ i for i in range(MAX_PID + 1)].remove(PID)
        self.symbols = random.shuffle(["X", "O"])
        self.moving = random.randint(2)

        for player in self.nodes:
            with grpc.insecure_channel(f"localhost:{PORTS[player]}") as channel:
                stub = tictactoe_pb2_grpc.TicTacToeStub(channel)
                message = tictactoe_pb2.StartingPlayerMessage(starting_node=self.nodes[self.moving], symbol=self.symbols[self.nodes.index(player)])
                stub.starting_player(message)
    
    def starting_player(self, request, context):
        print(f"Your symbol is {request.symbol}.")
        print(f"Node-{request.starting_node} goes first.")

class TicTacToeServer:
    def __init__(self):
        self.server = None
    def serve(self):
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
        tictactoe_pb2_grpc.add_TicTacToeServicer_to_server(TicTacToeServicer(), self.server)
        self.server.add_insecure_port(f'[::]:{PORTS[PID]}')
        self.server.start()
        print(f"Server started, CONNECTED to port {PORTS[PID]}")


class TicTacToeClient:
    def elect_leader(self):
        """Elect a node as a leader using the ring algorithm."""
        print(f"Starting elections")
        message = tictactoe_pb2.ElectionRequest(leader_pid=-1, candidate_pids=[PID])
        response = send_election_message(message)
        LEADER_PID = response.leader_pid
        print(f"Election complete. Coordinator is Node-{LEADER_PID}.")

        with grpc.insecure_channel(f"localhost:{PORTS[LEADER_PID]}") as channel:
            stub = tictactoe_pb2_grpc.TicTacToeStub(channel)
            response = stub.init_leader(tictactoe_pb2.InitLeaderRequest())
    
    def get_sync_time(self):
        """Retreive timestamps of all nodes, and return the average of their differences."""
        node_times = []
        for i, port in enumerate(PORTS):
            try:
                with grpc.insecure_channel(f"localhost:{port}") as channel:
                    stub = tictactoe_pb2_grpc.TicTacToeStub(channel)
                    response = stub.get_node_time(tictactoe_pb2.GetNodeTimeRequest())
                    node_times.append(response.timestamp)
            except grpc.RpcError as e:
                print(f"Node-{i} not responding: {e.details()}")  # Exception printed for debugging. Delete later.
        diffs = [e[1] - e[0] for e in combinations(node_times, 2)]
        return time() + (sum(diffs) / len(diffs))

    def synchronize_clocks(self):
        """Co-ordinate clocks between nodes using Berkeley's algorithm. Set synchronized time to server clocks."""
        print("Synchronizing clocks of all nodes")
        for i, port in enumerate(PORTS):
            try:
                with grpc.insecure_channel(f"localhost:{port}") as channel:
                    stub = tictactoe_pb2_grpc.TicTacToeStub(channel)
                    request = tictactoe_pb2.SetNodeTimeRequest(requester_pid=PID, target_pid=i, timestamp=self.get_sync_time())
                    response = stub.set_node_time(request)
                    print(response.message)
            except grpc.RpcError as e:
                print(f"Node-{i} not responding: {e.details()}")  # Exception printed for debugging. Delete later.

    def set_symbol(self, position, symbol):
        with grpc.insecure_channel(f"localhost:{PORTS[LEADER_PID]}") as channel:
            stub = tictactoe_pb2_grpc.TicTacToeStub(channel)
            request = tictactoe_pb2.SetSymbolRequest(symbol=symbol, position=int(position), timestamp=time()+TIME_DIFF)
            response = stub.set_symbol(request)
            if not response.success:
                print(response.message)

    def list_board(self):
        with grpc.insecure_channel(f"localhost:{PORTS[LEADER_PID]}") as channel:
            stub = tictactoe_pb2_grpc.TicTacToeStub(channel)
            request = tictactoe_pb2.ListBoardRequest()
            response = stub.list_board(request)
            print(response.board)




#--------- Utility functions ---------#

def get_next_node(pid):
    return (pid + 1) % (MAX_PID + 1)

def send_election_message(message):
    """Send election message to next working node."""
    next_pid = get_next_node(PID)
    while next_pid != PID:
        try:
            with grpc.insecure_channel(f"localhost:{PORTS[next_pid]}") as channel:
                stub = tictactoe_pb2_grpc.TicTacToeStub(channel)
                return stub.election(message)
        except grpc.RpcError as e:
            print(f"Node-{next_pid} not responding: {e.details()}")  # Exception printed for debugging. Delete later.
            next_pid = get_next_node(next_pid)
    return tictactoe_pb2.ElectionResponse(leader_pid=PID)

#-------------------------------------#

def main():
    client = TicTacToeClient()
    server = TicTacToeServer()
    thread = threading.Thread(target=server.serve)
    thread.start()
    sleep(2)  # Wait until server gets up and running

    print("Waiting for commands")
    while True:
        command = input(f"Node-{PID}> ").lower()
        if command == "start-game":
            client.synchronize_clocks()
            client.elect_leader()
        elif command == "stop":
            server.server.stop(0)
            break
        elif "set-symbol" in command:
            args = command.split(" ")
            client.set_symbol(args[1].stip(","), args[2])
        elif command == "list-board":
            client.list_board()
        elif command == "set-node-time":
            client.set_node_time()
        else:
            print("Command not found")


if __name__ == "__main__":
    main()
