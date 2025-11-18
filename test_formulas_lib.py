import formulas

# Test formula
formula = '=IF(OR(B5="",C5=""),"",B5*C5/100)'
values = {"B5": 1000, "C5": 10}

parser = formulas.Parser()
ast = parser.ast(formula)
print(f"AST: {ast}")

if ast[1]:
    func = ast[1].compile()
    result = func(values)
    print(f"Result: {result}")
