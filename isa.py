
# pylint: disable=invalid-name
# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-module-docstring

from enum import Enum
from typing import NamedTuple

OPCODE_SIZE = 5
REG_SIZE = 3
IMM_SIZE = 18

rd_m = 0b111_000_000_000000000000000000_00000
rs1_m = 0b000_111_000_000000000000000000_00000
rs2_m = 0b000_000_111_000000000000000000_00000
imm_m = 0b000_000_000_111111111111111111_00000
op_m = 0b000_000_000_000000000000000000_11111

rd_offs = REG_SIZE * 2 + IMM_SIZE + OPCODE_SIZE
rs1_offs = REG_SIZE + IMM_SIZE + OPCODE_SIZE
rs2_offs = IMM_SIZE + OPCODE_SIZE
imm_offs = OPCODE_SIZE
op_offs = 0
STDIN, STDOUT = 9999, 9998


class Instruction:
    @staticmethod
    def encode(opcode: int, args: list[int]) -> int:
        args.clear()
        return opcode

    @staticmethod
    def fetch_opcode(instr: int) -> int:
        return instr & op_m

    @staticmethod
    def fetch_rd(instr: int) -> int:
        return (instr & rd_m) >> rd_offs

    @staticmethod
    def fetch_rs1(instr: int) -> int:
        return (instr & rs1_m) >> rs1_offs

    @staticmethod
    def fetch_rs2(instr: int) -> int:
        return (instr & rs2_m) >> rs2_offs

    @staticmethod
    def fetch_imm(instr: int) -> int:
        return instr


class Register(Instruction):
    @staticmethod
    def encode(opcode: int, args: list[int]) -> int:
        instruct = 0
        instruct += (opcode << 0) & (op_m)
        instruct += (args[0] << rd_offs) & (rd_m)
        instruct += (args[1] << rs1_offs) & (rs1_m)
        instruct += (args[2] << rs2_offs) & (rs2_m)
        return instruct


class Immediate(Instruction):
    @staticmethod
    def encode(opcode: int, args: list[int]) -> int:
        instruct = 0
        instruct += (opcode << 0) & (op_m)
        instruct += (args[0] << rd_offs) & (rd_m)
        instruct += (args[1] << rs1_offs) & (rs1_m)
        instruct += (args[2] << imm_offs) & (imm_m)
        return instruct

    @staticmethod
    def fetch_imm(instr: int) -> int:
        return ((instr & (imm_m | rs2_m)) >> imm_offs)


class Branch(Instruction):
    @staticmethod
    def encode(opcode: int, args: list[int]) -> int:
        instruct = 0
        instruct += (opcode << 0) & (op_m)
        instruct += (args[0] << rs1_offs) & (rs1_m)
        instruct += (args[1] << rs2_offs) & (rs2_m)
        # add imm
        instruct += ((args[2] << imm_offs) & (rs2_m)) << (REG_SIZE * 2)
        instruct += ((args[2] << imm_offs) & (imm_m))

        return instruct

    @staticmethod
    def fetch_rd(instr: int) -> int:
        return (instr & rd_m) >> rd_offs

    @staticmethod
    def fetch_imm(instr: int) -> int:
        imm = (instr & imm_m) >> imm_offs
        imm += ((instr & rd_m) >> (REG_SIZE * 2)) >> imm_offs
        return imm


class Jump(Instruction):
    @staticmethod
    def encode(opcode: int, args: list[int]) -> int:
        instruct = (opcode << 0) & (op_m)
        instruct += (args[0] << imm_offs) & (imm_m)
        return instruct

    @staticmethod
    def fetch_imm(instr: int) -> int:
        return (instr & imm_m) >> imm_offs


class OpcodeFormat(NamedTuple):
    number: int
    instruction_type: type[Instruction]


class Opcode(OpcodeFormat, Enum):
    HALT = OpcodeFormat(number=0, instruction_type=Instruction)

    LW = OpcodeFormat(number=1, instruction_type=Register)
    SW = OpcodeFormat(number=2, instruction_type=Register)
    LWI = OpcodeFormat(number=3, instruction_type=Immediate)
    SWI = OpcodeFormat(number=4, instruction_type=Immediate)

    JMP = OpcodeFormat(number=5, instruction_type=Jump)

    BEQ = OpcodeFormat(number=6, instruction_type=Branch)
    BNE = OpcodeFormat(number=7, instruction_type=Branch)
    BLT = OpcodeFormat(number=8, instruction_type=Branch)
    BGT = OpcodeFormat(number=9, instruction_type=Branch)
    BNL = OpcodeFormat(number=10, instruction_type=Branch)
    BNG = OpcodeFormat(number=11, instruction_type=Branch)

    SEQ = OpcodeFormat(number=12, instruction_type=Register)
    SNE = OpcodeFormat(number=13, instruction_type=Register)
    SGT = OpcodeFormat(number=14, instruction_type=Register)
    SLT = OpcodeFormat(number=15, instruction_type=Register)
    SNL = OpcodeFormat(number=16, instruction_type=Register)
    SNG = OpcodeFormat(number=17, instruction_type=Register)
    AND = OpcodeFormat(number=18, instruction_type=Register)
    OR = OpcodeFormat(number=19, instruction_type=Register)
    ADD = OpcodeFormat(number=20, instruction_type=Register)
    SUB = OpcodeFormat(number=21, instruction_type=Register)
    MUL = OpcodeFormat(number=22, instruction_type=Register)
    DIV = OpcodeFormat(number=23, instruction_type=Register)
    REM = OpcodeFormat(number=24, instruction_type=Register)

    ADDI = OpcodeFormat(number=25, instruction_type=Immediate)
    MULI = OpcodeFormat(number=26, instruction_type=Immediate)
    SUBI = OpcodeFormat(number=27, instruction_type=Immediate)
    DIVI = OpcodeFormat(number=28, instruction_type=Immediate)
    REMI = OpcodeFormat(number=29, instruction_type=Immediate)


opcodes_by_number = dict((opcode.number, opcode) for opcode in Opcode)
opcodes_by_name = dict((opcode.name, opcode) for opcode in Opcode)


def normalize(code: list[dict]):
    normalized_code = []
    for instr in code:
        opcode = opcodes_by_name[instr["opcode"]]
        normalized_instr: dict[str, str | list[int]] = {
            "opcode": opcode.name}
        if opcode in [Opcode.SW, Opcode.SWI]:
            destination, source = instr["args"]
            normalized_instr["args"] = [0, destination, source]
        elif opcode is Opcode.LW:
            destination, source = instr["args"]
            normalized_instr["args"] = [destination, source, 0]
        elif opcode is Opcode.LWI:
            destination, source = instr["args"]
            normalized_instr["args"] = [destination, 0, source]
        else:
            normalized_instr["args"] = instr["args"]
        normalized_instr["args"] = list(
            map(int, normalized_instr["args"]))

        normalized_code.append(normalized_instr)
    return normalized_code


def encode_instr(instr):
    bin_instr = bytearray()
    opcode = opcodes_by_name[instr["opcode"]]
    args = [int(arg) for arg in instr["args"]]
    coded = opcode.instruction_type.encode(opcode.number, args)
    for _ in range(4):
        bin_instr.append(coded & 255)
        coded = coded >> 8
    return bytes(bin_instr)


def decode_opcode(instr: int) -> Opcode:
    return opcodes_by_number[Instruction.fetch_opcode(instr)]


def fetch_imm(instr: int) -> int:
    return decode_opcode(instr).instruction_type.fetch_imm(instr)


def format_instr(instr):
    opcode = decode_opcode(instr)
    rd = Instruction.fetch_rd(instr)
    rs1 = Instruction.fetch_rs1(instr)
    rs2 = Instruction.fetch_rs2(instr)
    imm = fetch_imm(instr)
    if opcode.instruction_type is Register:
        return f"{opcode.name} {rd}, {rs1}, {rs2}"
    if opcode.instruction_type is Immediate:
        return f"{opcode.name} {rd}, {rs1}, {imm}"
    if opcode.instruction_type is Branch:
        return f"{opcode.name} {rs1}, {rs2}, {imm}"
    if opcode.instruction_type is Jump:
        return f"{opcode.name} {imm}"
    return ""


def write_bin_code(target: str, data: list, code: list):
    """Записать машинный код в bin файл."""
    normalized = normalize(code)
    _start = len(data)
    program_start = bytearray()
    program_start.append(_start & 255)
    program_start.append((_start >> 8) & 255)
    program_start.append((_start >> 16) & 255)
    program_start.append((_start >> 24) & 255)

    program = bytearray(program_start)
    for value in map(int, data):
        for _ in range(4):
            program.append(value & 255)
            value = value >> 8
    for instr in normalized:
        program.extend(encode_instr(instr))
    with open(target, "wb") as file:
        file.write(program)

    return len(program)


def read_bin_code(target):
    memory = []
    with open(target, "rb") as file:
        while (bytes4 := file.read(4)):
            memory.append(int.from_bytes(bytes4, "little"))
    data = memory[1:memory[0] + 1]
    code = memory[memory[0] + 1:]
    return data, code
