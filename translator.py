#!/usr/bin/python3
# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-module-docstring
import re
import sys
from collections import deque
from collections.abc import Callable
from typing import Any, NamedTuple

from isa import STDIN, STDOUT, write_bin_code
from isa import Opcode as Opcode


def preprocess(raw: str) -> str:
    lines = []
    for line in raw.split("\n"):
        # remove comments
        comment_idx = line.find("#")
        if comment_idx != -1:
            line = line[:comment_idx]
        # remove leading spaces
        line = line.strip()
        lines.append(line)
    text = " ".join(lines)
    text = re.sub(r"[\n]", " ", text)
    return text


keyworlds = {"val", "while", "if"}
keychars = {";", ","}
operators = {
    "=": 0,
    "==": 1,
    "!=": 1,
    "<": 1,
    ">": 1,
    ">=": 1,
    "<=": 1,
    "&": 1,
    "|": 1,
    "+": 1,
    "-": 1,
    "*": 2,
    "/": 2,
    "%": 2,
    "@": 3
}
parenthesis = {
    "[": 4,
    "]": -4
}
brackets = {
    "(": 4,
    ")": -4
}

curly_braces = {
    "{": 4,
    "}": -4
}

breakers = set().union(operators) \
    .union(parenthesis).union(brackets) \
    .union(curly_braces).union(keychars)
breakers.add(";")

breakers_by_length: dict[int, set[str]] = {0: set()}


def get_breaker_by_length(breaker_length):
    return set(
        map(lambda breaker: breaker[:breaker_length], filter(
            lambda breaker: len(breaker) >= length,
            breakers))
    )


for length in range(1, max(map(len, breakers)) + 1):
    breakers_by_length[length] = get_breaker_by_length(length)
breakers_by_length[max(list(breakers_by_length)) + 1] = set()


def tokenize(processed_text):
    # parts will contain part of source text divided by "'"
    # every uneven part is a string literal and that don't need to tokenize
    # thus it's a token byself
    parts: deque[str] = deque()
    part_start_idx = 0
    for char_idx, char in enumerate(processed_text):
        if char == "'":
            if char_idx > 0 and processed_text[char_idx - 1] != "\\":
                parts.append(processed_text[part_start_idx:char_idx])
                part_start_idx = char_idx + 1
    parts.append(processed_text[part_start_idx:])

    tokens: deque[str] = deque()

    for part_idx, part in enumerate(parts):
        if part_idx % 2 == 0:
            # such difficulty only for one sort of cases: =,!=,==
            npart = bytearray()
            keyword = bytearray()
            for char in part:
                if keyword:
                    if f"{keyword.decode('utf-8')}{char}" in breakers_by_length[len(keyword) + 1]:
                        keyword.append(ord(char))
                    else:
                        if keyword.decode("utf-8") in breakers:
                            npart.append(ord(" "))
                            npart.extend(keyword)
                            npart.append(ord(" "))
                            keyword.clear()
                        else:
                            npart.extend(keyword)
                            keyword.clear()
                        npart.append(ord(char))
                elif char in breakers_by_length[1]:
                    keyword.append(ord(char))
                else:
                    npart.append(ord(char))

            part = npart.decode("utf-8")

            part = part.replace("[", " @ [")
            part = part.replace("]", " ] ")

            part = re.sub("[ ]+", " ", part)

            tokens.extend(filter(lambda token: token, part.split(" ")))
        else:
            tokens.append(f"'{part}'")
    return list(tokens)


class ASTParserUnit:
    """
    Intermediate Representation
    """

    def __init__(self) -> None:
        self.terms: deque = deque()
        self.nesting_level: deque = deque()

    def getCurrentTerm(self) -> deque:
        max_level = len(self.nesting_level)
        if max_level == 0:
            return self.terms
        term = self.terms[self.nesting_level[0]]
        for i in range(1, max_level):
            if isinstance(term[self.nesting_level[i]], list):
                term = term[self.nesting_level[i]]
            else:
                return term
        return term

    def driveIn(self):
        term = self.getCurrentTerm()
        term.append([])
        self.nesting_level.append(len(term) - 1)

    def addToken(self, token):
        self.getCurrentTerm().append(token)

    def driveOut(self):
        term = self.getCurrentTerm()
        if term and not term[-1]:
            term.pop()
        self.nesting_level.pop()

    def exportTerms(self):
        if self.terms and not self.terms[-1]:
            self.terms.pop()
        return list(self.terms)


def buildAST(tokens: list[str]):
    # memorized all variables
    parseUnit = ASTParserUnit()
    parseUnit.driveIn()
    for token in tokens:
        if token in ["if", "while"]:
            parseUnit.addToken(token)
        elif token == "(":
            parseUnit.driveIn()
        elif token == "{":
            parseUnit.driveIn()
            parseUnit.driveIn()
        elif token == ")":
            parseUnit.driveOut()
        elif token == "}":
            parseUnit.driveOut()
            parseUnit.driveOut()
            parseUnit.driveOut()
            parseUnit.driveIn()
        elif token == ";":
            parseUnit.driveOut()
            parseUnit.driveIn()
        else:
            parseUnit.addToken(token)

    return parseUnit.exportTerms()


class Expression(NamedTuple):
    left: str | Any
    right: str | Any
    operation: Callable[[str, str], str]


PRIOR = 0
OP = 1
INDEX = 1


def last_min_op(exprs):
    last = 0
    for expr_idx, expr in enumerate(exprs):
        if expr[PRIOR] <= exprs[last][PRIOR]:
            last = expr_idx
    return last


def parse_expression(tokens):
    # linearization
    while any(map(lambda token: isinstance(token, list), tokens)):
        linearized_tokens = deque()
        for token in tokens:
            if isinstance(token, list):
                linearized_tokens.append("(")
                linearized_tokens.extend(token)
                linearized_tokens.append(")")
            else:
                linearized_tokens.append(token)
        tokens = linearized_tokens
    operation_priority = 0
    expr = deque()
    ops: deque[tuple] = deque()
    for token_idx, token in enumerate(tokens):
        if token in brackets:
            operation_priority += brackets[token]
        elif token in parenthesis:
            operation_priority += parenthesis[token]
        elif token in operators:
            priority = operation_priority + operators[token]
            expr.append((priority, token))
        else:
            expr.append(token)
    for token_idx, token in enumerate(expr):
        if isinstance(token, tuple):
            ops.append((token[0], token_idx))
    expr = list(expr)

    def resolve(ops: list[tuple]):
        op_ptr = last_min_op(ops)
        if op_ptr == len(ops) - 1:
            right = expr[ops[op_ptr][INDEX] + 1]
        else:
            right = resolve(ops[op_ptr + 1:])
        if op_ptr == 0:
            left = expr[ops[op_ptr][INDEX] - 1]
        else:
            left = resolve(ops[:op_ptr])

        return (expr[ops[op_ptr][INDEX]][OP], left, right)

    return resolve(list(ops)) if len(ops) else tokens[0]


class Translator:
    ARGS = "args"
    OPCODE = "opcode"
    FISH = "undefined_address"

    def __init__(self) -> None:
        self.program: deque = deque()
        self.vars: dict[str, Any] = {}
        self.memory: deque = deque()
        self.data_address = 0
        [self.X0, self.X1, self.X2, self.X3, self.SP] = ["0", "1", "2", "3", "4"]
        self.op = {}
        self.pc = 0
        self.unresolved_addresses: deque = deque()
        for opcode in list(Opcode):
            # print(opcode.name)
            self.op[opcode.name] = self.generate_commands(opcode.name)

    def generate_commands(self, opcode):

        def insert_command(rt=None, rla=None, rrb=None):
            args = []
            for arg in rt, rla, rrb:
                if arg is not None:
                    args.append(arg)
            self.program.append(
                {
                    self.OPCODE: opcode,
                    self.ARGS: args
                }
            )
            self.pc += 1

        return insert_command

    def append_unresolved_address(self):
        self.unresolved_addresses.append(self.pc - 1)

    def resolve_address(self):
        address = self.unresolved_addresses.pop()
        self.program[address][self.ARGS][2] = self.pc

    def solve(self, expr):
        if isinstance(expr, tuple):
            operation, left, right = expr
            self.solve(left)
            self.solve(right)
            if operation == "@":
                self.op["ADDI"](self.SP, self.SP, 1)
                self.op["LW"](self.X2, self.SP)
                self.op["ADDI"](self.SP, self.SP, 1)
                self.op["LW"](self.X1, self.SP)
                self.op["ADD"](self.X3, self.X1, self.X2)
                self.op["LW"](self.X1, self.X3)
                self.op["SW"](self.SP, self.X1)
                self.op["SUBI"](self.SP, self.SP, 1)

            else:
                self.op["ADDI"](self.SP, self.SP, 1)
                self.op["LW"](self.X2, self.SP)
                self.op["ADDI"](self.SP, self.SP, 1)
                self.op["LW"](self.X1, self.SP)

                if operation == "==":
                    self.op["SEQ"](self.X3, self.X1, self.X2)
                elif operation == "!=":
                    self.op["SNE"](self.X3, self.X1, self.X2)
                elif operation == ">":
                    self.op["SGT"](self.X3, self.X1, self.X2)
                elif operation == "<":
                    self.op["SLT"](self.X3, self.X1, self.X2)
                elif operation == ">=":
                    self.op["SNL"](self.X3, self.X1, self.X2)
                elif operation == "<=":
                    self.op["SNG"](self.X3, self.X1, self.X2)
                elif operation == "&":
                    self.op["AND"](self.X3, self.X1, self.X2)
                elif operation == "|":
                    self.op["OR"](self.X3, self.X1, self.X2)
                elif operation == "+":
                    self.op["ADD"](self.X3, self.X1, self.X2)
                elif operation == "-":
                    self.op["SUB"](self.X3, self.X1, self.X2)
                elif operation == "*":
                    self.op["MUL"](self.X3, self.X1, self.X2)
                elif operation == "/":
                    self.op["DIV"](self.X3, self.X1, self.X2)
                elif operation == "%":
                    self.op["REM"](self.X3, self.X1, self.X2)

                self.op["SW"](self.SP, self.X3)
                self.op["SUBI"](self.SP, self.SP, 1)
        else:
            if expr.isdigit():
                self.op["SWI"](self.SP, int(expr))
                self.op["SUBI"](self.SP, self.SP, 1)
            elif expr in self.vars:
                self.op["LWI"](self.X1, self.vars[expr])
                self.op["SW"](self.SP, self.X1)
                self.op["SUBI"](self.SP, self.SP, 1)

    def addr(self, addr):
        if isinstance(addr, tuple):
            _, left, right = addr
            self.solve(left)
            self.solve(right)
            self.op["ADDI"](self.SP, self.SP, 1)
            self.op["LW"](self.X2, self.SP)
            self.op["ADDI"](self.SP, self.SP, 1)
            self.op["LW"](self.X1, self.SP)
            self.op["ADD"](self.X3, self.X1, self.X2)
            self.op["SW"](self.SP, self.X3)
            self.op["SUBI"](self.SP, self.SP, 1)
        else:
            self.op["ADDI"](self.X1, self.X0, self.vars[addr])
            self.op["SW"](self.SP, self.X1)
            self.op["SUBI"](self.SP, self.SP, 1)

    def allocate(self, term: list):
        if term[0] == "val":
            variable = term[1]
            if len(term) > 5 and (term[3], term[5]) == ("[", "]"):
                self.vars[variable] = self.data_address
                self.data_address += 1
                self.memory.append(self.data_address)

                self.data_address += int(term[4])
                if len(term) > 6:

                    if isinstance(term[7], list):
                        inits = list(filter(lambda val: val != ",", term[7]))
                        self.memory.extend(map(int, inits))
                        self.memory.extend([0] * (int(term[4]) - len(inits)))
                    elif (term[7][0], term[7][-1]) == ("'", "'"):
                        inits = list(map(ord, term[7][1:-1]))
                        self.memory.extend(map(int, inits))
                        self.memory.extend([0] * (int(term[4]) - len(inits)))

                else:
                    self.memory.extend([0] * int(term[4]))
            else:
                self.vars[variable] = self.data_address
                self.data_address += 1
                if len(term) > 2 and term[2] == "=":
                    value = term[3]
                    if value.isdigit():
                        self.memory.append(int(value))
                    else:
                        self.memory.append(self.memory[self.vars[variable]])
                else:
                    self.memory.append(0)

    def _translate_(self, term: list):
        if not term or term[0] == "val":
            return
        if term[0] in ["if", "while"]:
            # print(f"{type(term)} {term}")
            keyword = term[0]
            condition = term[1]
            body = term[2]
            condition_start = self.pc
            self.solve(parse_expression(condition))
            self.op["ADDI"](self.SP, self.SP, 1)
            self.op["LW"](self.X1, self.SP)
            self.op["BEQ"](self.X1, self.X0, self.FISH)
            self.append_unresolved_address()
            # block init

            for _term_ in body:
                if _term_ != "&":
                    if _term_ and isinstance(_term_[0], list) and _term_[0][0] == "if":
                        _term_ = _term_[0]
                    self._translate_(_term_)

            # end blocks
            if keyword == "while":
                self.op["JMP"](condition_start)
            self.resolve_address()
        elif term[0] == "get":
            mvalue = parse_expression(term[1:])
            self.addr(mvalue)
            self.op["ADDI"](self.SP, self.SP, 1)
            self.op["LW"](self.X1, self.SP)
            self.op["LWI"](self.X3, STDIN)
            self.op["SW"](self.X1, self.X3)
        elif term[0] == "put":
            if term[1].isdigit():
                self.op["ADDI"](self.X1, self.X0, term[1])
            else:
                vvalue = parse_expression(term[1:])
                self.solve(vvalue)
                self.op["ADDI"](self.SP, self.SP, 1)
                self.op["LW"](self.X1, self.SP)
            self.op["ADDI"](self.X2, self.X0, STDOUT)
            # self.op["ADDI"](self.X1, self.X1, ord('0'))
            self.op["SW"](self.X2, self.X1)

        elif term[0] == "gets":
            self.op["LWI"](self.X2, self.vars[term[1]])
            self.op["LWI"](self.X1, STDIN)
            self.op["BEQ"](self.X1, self.X0, self.FISH)
            self.append_unresolved_address()
            self.op["SW"](self.X2, self.X1)
            self.op["ADDI"](self.X2, self.X2, 1)
            self.op["JMP"](self.pc - 4)
            self.resolve_address()
        elif term[0] == "puts":
            if (term[1][0], term[1][-1]) == ("'", "'"):
                self.op["SW"](self.SP, self.X0)
                self.op["ADD"](self.X3, self.SP, self.X0)
                self.op["SUBI"](self.SP, self.SP, 1)
                for character in (term[1])[1:-1]:
                    self.op["ADDI"](self.X1, self.X0, ord(character))
                    self.op["SW"](self.SP, self.X1)
                    self.op["SUBI"](self.SP, self.SP, 1)
                # write string
                self.op["ADD"](self.SP, self.X3, self.X0)

                self.op["SUBI"](self.SP, self.SP, 1)
                self.op["LW"](self.X1, self.SP)
                self.op["SW"](self.SP, self.X0)
                self.op["BEQ"](self.X1, self.X0, self.FISH)
                self.append_unresolved_address()

                self.op["ADDI"](self.X2, self.X0, STDOUT)
                self.op["SW"](self.X2, self.X1)

                self.op["JMP"](self.pc - 6)

                self.resolve_address()

                self.op["ADD"](self.SP, self.X3, self.X0)
            else:
                self.op["LWI"](
                    self.X2, self.vars[term[1]])
                self.op["LW"](self.X1, self.X2)
                self.op["BEQ"](self.X1, self.X0, self.FISH)
                self.append_unresolved_address()

                self.op["ADDI"](self.X3, self.X0, STDOUT)
                self.op["SW"](self.X3, self.X1)
                self.op["ADDI"](self.X2, self.X2, 1)
                self.op["JMP"](self.pc - 5)
                self.resolve_address()
        else:
            operation = term.index("=")
            mvalue = parse_expression(term[:operation])
            expression = parse_expression(term[operation + 1:])
            self.addr(mvalue)
            if (expression[0], expression[-1]) == ("'", "'"):
                self.op["ADDI"](self.SP, self.SP, 1)
                self.op["LW"](self.X2, self.SP)
                self.op["LW"](self.X3, self.X2)
                for char in expression[1:-1]:
                    self.op["SWI"](self.X3, ord(char))
                    self.op["ADDI"](self.X3, self.X3, 1)
            else:
                self.solve(expression)
                self.op["ADDI"](self.SP, self.SP, 1)
                self.op["LW"](self.X2, self.SP)
                self.op["ADDI"](self.SP, self.SP, 1)
                self.op["LW"](self.X1, self.SP)
                self.op["SW"](self.X1, self.X2)

    def translate(self, terms):
        self.program = deque()
        self.unresolved_addresses = deque()
        for term in terms:
            self.allocate(term)
        # print(f"{self.vars}\n{self.memory}\n{self.data_address}")
        # self.pc = len(self.memory)
        self.pc = 0
        # self.program.extend(list(self.memory))
        for term in terms:
            self._translate_(term)

        self.op["HALT"]()
        return list(self.memory), list(self.program), self.vars


def main(args):
    assert len(args) == 2, \
        "Wrong arguments: translator.py <input_file> <target_bin_file>"

    source, target_bin = args

    with open(source, encoding="utf-8") as f:
        source = f.read()

    text = preprocess(source)
    tokens = tokenize(text)
    ast = buildAST(tokens)
    memory, program, data = Translator().translate(ast)
    print("source LoC:", len(source.split()), "code instr:",
          len(program))
    write_bin_code(target_bin, memory, program)

if __name__ == "__main__":
    main(sys.argv[1:])
