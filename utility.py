from concurrent import futures
import grpc
import datetime
import itertools
import sys
import time

import tictactoe_pb2
import tictactoe_pb2_grpc


def pass_election_message(message, current_pid, ports):
    """Try to pass election message to successor. If successor doesn't respond, try the next in line."""
    for i in itertools.chain(range(current_pid + 1, len(ports)), range(current_pid)):
        try:
            channel = grpc.insecure_channel(f"localhost:{ports[i]}")  # TODO Mis siia localhost asemele tuleb?
            stub = tictactoe_pb2_grpc.TicTacToeStub(channel)
            return stub.elect(message)
        except:
            continue
    return tictactoe_pb2.ElectionResponse(leader_pid=current_pid)
