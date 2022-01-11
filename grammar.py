class Grammar:
    """ парсинг файла с правилами грамматики
    """

    def __init__(self, grammar_str):
        self.grammar_str = '\n'.join(filter(None, grammar_str.splitlines()))
        self.grammar = {}
        self.start = None
        self.terminals = set()
        self.nonterminals = set()

        # построчный разбор грамматики, каждая строка - продукция
        for production in list(filter(None, grammar_str.splitlines())):
            head, _, bodies = production.partition(' -> ')

            # нетерминалом может быть только заглавная буква
            if not head.isupper():
                raise ValueError(
                    f'\'{head} -> {bodies}\': \'{head}\' - не заглавная буква и не может считаться нетерминалом.')

            # первый нетерминал назначается стартовым
            if not self.start:
                self.start = head

            # дефолтное значение ключа - текущий нетерминал
            self.grammar.setdefault(head, set())
            # текущий нетерминал добавляется во множество нетерминалов
            self.nonterminals.add(head)
            # правая часть продукции разбивается на множество кортежей
            bodies = {tuple(body.split()) for body in bodies.split('|')}

            for body in bodies:
                if '^' in body and body != ('^',):
                    raise ValueError(f'\'{head} -> {" ".join(body)}\': Символ Null \'^\' не допустим в этом месте.')
                self.grammar[head].add(body)

                # составляем список терминалов и нетерминалов
                for symbol in body:
                    if not symbol.isupper() and symbol != '^':
                        self.terminals.add(symbol)
                    elif symbol.isupper():
                        self.nonterminals.add(symbol)

        self.symbols = self.terminals | self.nonterminals
