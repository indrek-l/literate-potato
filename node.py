from concurrent import futures
import grpc
from datetime import datetime
import sys
import time
import threading

import tictactoe_pb2
import tictactoe_pb2_grpc

from utility import pass_election_message

# Pordid peaksid vist olema saladused seal saladuste hoidlas, mille eest lisapunkte saab
MAX_PID = 2
PORTS = []
for i in range(MAX_PID + 1):
    PORTS.append(20040 + i)

COORDINATOR = -1
PID = -1


class TicTacToeServicer(tictactoe_pb2_grpc.TicTacToeServicer):
    def __init__(self, pid):
        self.pid = pid
        self.time_drift = 0

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
    
    def get_node_time(self, request, context):
        pass

    def election(self, request, context):
        initiator = request.candidate_pids[0]
        if self.pid == initiator:
            if request.leader_pid == -1:
                highest_pid = max(request.candidate_pids)
                if self.pid == highest_pid:
                    return tictactoe_pb2.ElectionResponse(leader_pid=self.pid)
                leader_message = tictactoe_pb2.ElectionRequest(leader_pid=highest_pid, candidate_pids=[self.pid])
                return send_election_message(leader_message, self.pid)            
            if request.leader_pid in request.candidate_pids:
                return tictactoe_pb2.ElectionResponse(leader_pid=request.leader_pid)
            print("Election unsuccesful. Restarting.")
            return self.election(tictactoe_pb2.ElectionRequest(leader_pid=-1, candidate_pids=[self.pid]))
        request.candidate_pids.append(self.pid)
        return send_election_message(request, self.pid)


class TicTacToeServer:
    def __init__(self, pid):
        self.pid = pid

    def serve(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
        tictactoe_pb2_grpc.add_TicTacToeServicer_to_server(TicTacToeServicer(self.pid), server)
        server.add_insecure_port(f'[::]:{PORTS[self.pid]}')
        server.start()
        print(f"Server started, CONNECTED to port {PORTS[self.pid]}")
        server.wait_for_termination()


class TicTacToeClient:
    def __init__(self, pid):
        self.pid = pid

    def elect_leader(self):
        """Elect a node as a leader using the ring algorithm."""
        print(f"Starting elections")
        message = tictactoe_pb2.ElectionRequest(leader_pid=-1, candidate_pids=[self.pid])
        response = send_election_message(message, self.pid)
        print(f"Election complete. Coordinator is Node-{response.leader_pid}.")
        self.leader_pid = response.leader_pid
    
    def synchronize_clocks(self, pid):
        """Co-ordinate clocks between nodes using Berkeley's algorithm."""
        print("Synchronizing clocks of all nodes")



#--------- Utility functions ---------#

def get_next_node(pid):
    return (pid + 1) % (MAX_PID + 1)

def send_election_message(message, current_pid):
    """Send election message to next working node."""
    next_pid = get_next_node(current_pid)
    while next_pid != current_pid:
        try:
            with grpc.insecure_channel(f"localhost:{PORTS[next_pid]}") as channel:
                stub = tictactoe_pb2_grpc.TicTacToeStub(channel)
                return stub.election(message)
        except grpc.RpcError:
            print(f"Node-{next_pid} not responding.")
            next_pid = get_next_node(next_pid)
    return tictactoe_pb2.ElectionResponse(leader_pid=current_pid)

#-------------------------------------#

def main():
    pid = int(sys.argv[1])
    client = TicTacToeClient(pid)
    server = TicTacToeServer(pid)
    threading.Thread(target=server.serve).start()
    time.sleep(2)  # Wait until server gets up and running

    print("Waiting for commands")
    command = input(f"Node-{pid}> ")
    if command.lower() == "start-game":
        client.elect_leader()
    else:
        print("Command not found")


if __name__ == "__main__":
    main()
