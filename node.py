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
CLOCK = -1
LEADER_PID = -1

class TicTacToeServicer(tictactoe_pb2_grpc.TicTacToeServicer):
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
        if request.requester_pid == LEADER_PID or LEADER_PID == -1: # :unamused:
            CLOCK = request.timestamp
            return tictactoe_pb2.SetNodeTimeResponse(message=f"Node-{PID} new clock {datetime.fromtimestamp(CLOCK).strftime('%H:%m:%S')}")
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


class TicTacToeServer:
    def serve(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
        tictactoe_pb2_grpc.add_TicTacToeServicer_to_server(TicTacToeServicer(), server)
        server.add_insecure_port(f'[::]:{PORTS[PID]}')
        server.start()
        print(f"Server started, CONNECTED to port {PORTS[PID]}")
        server.wait_for_termination()


class TicTacToeClient:
    def elect_leader(self):
        """Elect a node as a leader using the ring algorithm."""
        print(f"Starting elections")
        message = tictactoe_pb2.ElectionRequest(leader_pid=-1, candidate_pids=[PID])
        response = send_election_message(message)
        LEADER_PID = response.leader_pid
        print(f"Election complete. Coordinator is Node-{LEADER_PID}.")
    
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
        return time() + sum(diffs) / len(diffs)

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
                print(f"Node-{i} not responding: {e}")  # Exception printed for debugging. Delete later.



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
    threading.Thread(target=server.serve).start()  # TODO: Kuidas lõimes jooksev server kinni panna käsurealt?
    sleep(2)  # Wait until server gets up and running

    print("Waiting for commands")
    command = input(f"Node-{PID}> ")
    if command.lower() == "start-game":
        client.synchronize_clocks()
        client.elect_leader()
    else:
        print("Command not found")


if __name__ == "__main__":
    main()
