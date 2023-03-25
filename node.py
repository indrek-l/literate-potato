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
PORTS = []
for i in range(MAX_PID + 1):
    PORTS.append(20040 + i)

COORDINATOR = -1
PID = -1


class TicTacToeServicer(tictactoe_pb2_grpc.TicTacToeServicer):
    def __init__(self, pid):
        self.pid = pid
        self.leader_pid = -1
        self.time_drift = 0

    def set_symbol(self, request, context):
        pass
    
    def list_board(self, request, context):
        pass
        
    def check_winner(self, request, context):
        pass
    
    def check_timeout(self, request, context):
        pass
    
    def get_node_time(self, request, context):
        return tictactoe_pb2.GetNodeTimeResponse(timestamp=time())
    
    def set_node_time(self, request, context):
        if request.requester_pid == self.leader_pid:
            self.clock = request.timestamp
            print(f"Node-{self.pid} new clock {datetime.fromtimestamp(self.clock).strftime('%H:%m:%S')}")
        else:
            print(f"Only the game master (Node-{self.leader_pid}) can modify the clock of Node-{self.pid}")

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
                self.leader_pid = request.leader_pid # Leader found
                return tictactoe_pb2.ElectionResponse(leader_pid=request.leader_pid)
            print("Election unsuccesful. Restarting.")
            return self.election(tictactoe_pb2.ElectionRequest(leader_pid=-1, candidate_pids=[self.pid]))
        # Current node did not initiate election. Pass the message on.
        request.candidate_pids.append(self.pid)
        response = send_election_message(request, self.pid)
        if response.leader_pid > -1:
            # Record the leader as the message returns.
            self.leader_pid = response.leader_pid
        return send_election_message(request, self.pid)


class TicTacToeServer:
    def __init__(self, pid):
        self.pid = pid
        self.clock = -1
        self.leader_pid = -1

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
        self.leader_pid = -1

    def elect_leader(self):
        """Elect a node as a leader using the ring algorithm."""
        print(f"Starting elections")
        message = tictactoe_pb2.ElectionRequest(leader_pid=-1, candidate_pids=[self.pid])
        response = send_election_message(message, self.pid)
        print(f"Election complete. Coordinator is Node-{response.leader_pid}.")
        self.leader_pid = response.leader_pid
    
    def get_sync_time(self):
        """Retreive timestamps of all nodes, and return the average of their differences."""
        node_times = [time()]
        for i, port in enumerate(PORTS):
            try:
                with grpc.insecure_channel(f"localhost:{port}") as channel:
                    stub = tictactoe_pb2_grpc.TicTacToeStub(channel)
                    response = stub.get_node_time(tictactoe_pb2.GetNodeTimeRequest())
                    node_times.append(response.timestamp)
            except grpc.RpcError:
                print(f"Node-{i} not responding.")
        diffs = [e[1] - e[0] for e in combinations(node_times, 2)]
        return datetime.fromtimestamp(time() + sum(diffs) / len(diffs))  # TODO: Siin tuleb ZeroDivisionError

    def synchronize_clocks(self):
        """Co-ordinate clocks between nodes using Berkeley's algorithm. Set synchronized time to server clocks."""
        print("Synchronizing clocks of all nodes")
        sync_time = self.get_sync_time()
        for i, port in enumerate(PORTS):  # Also set your own server clock to sync time.
            try:
                with grpc.insecure_channel(f"localhost:{port}") as channel:
                    stub = tictactoe_pb2_grpc.TicTacToeStub(channel)
                    request = tictactoe_pb2.SetNodeTimeRequest(requester_pid=self.pid, target_pid=i, timestamp=sync_time)
                    stub.set_node_time(request)
            except grpc.RpcError:
                print(f"Node-{i} not responding.")



#--------- Utility functions ---------#

def get_next_node(pid):
    return (pid + 1) % (MAX_PID + 1)

def send_election_message(message, current_pid):
    """Send election message to next working node."""
    while (next_pid := get_next_node(current_pid)) != current_pid:
        try:
            with grpc.insecure_channel(f"localhost:{PORTS[next_pid]}") as channel:
                stub = tictactoe_pb2_grpc.TicTacToeStub(channel)
                return stub.election(message)
        except grpc.RpcError:
            print(f"Node-{next_pid} not responding.")
    return tictactoe_pb2.ElectionResponse(leader_pid=current_pid)

#-------------------------------------#

def main():
    pid = int(sys.argv[1])
    client = TicTacToeClient(pid)
    server = TicTacToeServer(pid)
    threading.Thread(target=server.serve).start()
    sleep(2)  # Wait until server gets up and running

    print("Waiting for commands")
    command = input(f"Node-{pid}> ")
    if command.lower() == "start-game":
        client.synchronize_clocks()
        client.elect_leader()
    else:
        print("Command not found")


if __name__ == "__main__":
    main()
