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
PORTS = []
for i in range(MAX_PID + 1):
    PORTS.append(20040 + i)

COORDINATOR = -1
PID = -1

def get_next_node(PID):
    return (PID + 1) % (MAX_PID + 1)

def send_start_message(message):
    next_node = get_next_node(PID)
    while next_node != PID:
        # find a next node that is working
        try:
            with grpc.insecure_channel('localhost:'+str(PORTS[next_node])) as channel:
                # send message to the next node
                print(f"Sending message to node {next_node} on port {PORTS[next_node]}")
                stub = tictactoe_pb2_grpc.TicTacToeStub(channel)
                response = stub.start_game(message)
                return response
            
        except grpc.RpcError as e:
            print(f"node {next_node} not responding")
            # try the next node in the ring
            next_node = get_next_node(next_node)
    

class TicTacToeServicer(tictactoe_pb2_grpc.TicTacToeServicer):
    def __init__(self):
        self.time_drift = 0
    
    def start_game(self, request, context):
        print("resieved start_game request")

        if request.initiator_node == PID:
            if request.coordinator_node == -1:
                for node in request.candidate_nodes:
                    if node >  COORDINATOR:
                         COORDINATOR = node

                message = tictactoe_pb2.StartGameRequest(initiator_node=PID, coordinator_node=COORDINATOR, candidate_nodes=[PID]) #TODO timestamp <hh:mm:ss>
                response = send_start_message(message)

            else:
                response = tictactoe_pb2.StartGameResponse()
                response.coordinator_node = PID
                if COORDINATOR in response.candidate_nodes:
                    response.election_succesful = True
                response.timestamp = time.time()
                    
        else:
            request.candidate_nodes.append(self.outer_self.process_id)
            message = tictactoe_pb2.StartGameRequest(initiator_node=PID, coordinator_node=request.coordinator_node, candidate_nodes=request.candidate_nodes.append) #TODO timestamp <hh:mm:ss>
            response = send_start_message(message)
            if response.election_succesful:
                COORDINATOR = response.coordinator_node
        
        return response

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

    def serve(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
        tictactoe_pb2_grpc.add_TicTacToeServicer_to_server(TicTacToeServicer(), server)
        server.add_insecure_port(f'[::]:{PORTS[PID]}')
        server.start()
        print(f"Server started, CONNECTED to port {PORTS[PID]}")
        return server


class TicTacToeClient:

    def start_elections(self):
        print(f"Starting elections")
        message = tictactoe_pb2.StartGameRequest(initiator_node=PID, candidate_nodes=[PID]) #TODO timestamp <hh:mm:ss>
        response = send_start_message(message)

        while not response.election_succesful:
            response = send_start_message(message)

        print(f"Election completed successfully. Coordinator ID is {response.leader_id}")
        self.leader_id = response.leader_id

        if self.leader_id == None:
            print("No other nodes working. I am the leader")
            self.leader_id = PID
        

def main():
    client = TicTacToeClient()
    server = TicTacToeServer()
    server.serve()

    print("Waiting for commands")
    command = input(f"Node-{PID}> ")
    if command.lower() == "start-game":
        client.start_elections()
    else:
        print("Command not found")



if __name__ == "__main__":
    PID = int(sys.argv[1])
    main()
