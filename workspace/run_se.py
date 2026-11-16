import argparse
import inspect

# Importing any gem5 components we will use to build the system
from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.cachehierarchies.classic.private_l1_private_l2_cache_hierarchy import (
    PrivateL1PrivateL2CacheHierarchy,
)
from gem5.components.memory import SingleChannelDDR3_1600
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA
from gem5.resources.resource import BinaryResource
from gem5.simulate.simulator import Simulator

# Simple argument parsing to make parameter sweep and binary selection easier
parser = argparse.ArgumentParser()
parser.add_argument("binary")
parser.add_argument("--vlen", type=int, default=256, help="vector length in bits")
parser.add_argument("--elen", type=int, default=64)
args = parser.parse_args()

# configuring each core to have its own L1+L2 caches
cache = PrivateL1PrivateL2CacheHierarchy(
    l1d_size="32KiB",
    l1i_size="32KiB",
    l2_size="256KiB",
)

# Configuring memory
mem = SingleChannelDDR3_1600(size="512MiB")

# Building a processory (Out-of-Order, RISC-V ISA, 1 core, etc...)
proc = SimpleProcessor(
    cpu_type=CPUTypes.O3,
    clk_freq="3GHz",
    num_cores=1,
    isa=ISA.RISCV,
)

# Combining all these parts into a system
board = SimpleBoard(
    memory=mem,
    # Honestly not sure why it's having me repeat this, but it was throwing errors
    clk_freq="3GHz",
    cache_hierarchy=cache,
    processor=proc,
)

# Setting the vector parameters (only 1 core)
isa = proc.cores[0].core.isa[0]
isa.vlen = args.vlen
isa.elen = args.elen

# Telling gem5 what to run (either binary with vector instructions or scalar instructions)
board.set_se_binary_workload(BinaryResource(local_path=args.binary))

# Running simulation
simulator = Simulator(board=board)
simulator.run()
print(f"Finished at tick {simulator.get_current_tick()}")
