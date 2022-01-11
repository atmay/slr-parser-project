from graphviz import Digraph
import argparse

from grammar import Grammar


def union(set1, set2):
    """ вспомогательный метод для проверки, добавились ли новые символы во множество"""
    set1_len = len(set1)
    # добавляем сет2 в сет1
    set1 |= set2
    return set1_len != len(set1)


def first_follow(G):
    """Построение множеств follow для каждого
    """

    # создается словарь с ключами-символами, для каждого символа грамматики создается пустое множество
    first = {symbol: set() for symbol in G.symbols}
    # для терминалов создаем множество, содержащее сам терминал
    first.update((terminal, {terminal}) for terminal in G.terminals)

    # создается словарь с ключами-нетерминалами, для каждого нетерминала создается пустое множество
    follow = {symbol: set() for symbol in G.nonterminals}
    # для стартового нетерминала добавляется символ конца строки
    follow[G.start].add('$')

    while True:
        # создаем переменную-флаг для определения изменений
        updated = False

        for head, bodies in G.grammar.items():
            for body in bodies:
                for symbol in body:
                    # для каждого значащего (непустого) символа
                    # добавляем first к first нетерминала (левой стороне продукции) и исключаем незначащие символы
                    if symbol != '^':
                        updated |= union(first[head], first[symbol] - set('^'))
                        if '^' not in first[symbol]:
                            break
                    else:
                        updated |= union(first[head], set('^'))
                else:
                    # добавляем ^ к сету
                    updated |= union(first[head], set('^'))

                head_follow = follow[head]
                # справа налево разбираем правые части продукций
                for symbol in reversed(body):
                    if symbol == '^':
                        continue
                    if symbol in follow:
                        updated |= union(follow[symbol], head_follow - set('^'))
                    if '^' in first[symbol]:
                        head_follow = head_follow | first[symbol]
                    else:
                        head_follow = first[symbol]

        # выходим из циклв после добавления в first и follow всех возможных вариантов
        if not updated:
            return first, follow


class SLRParser:
    def __init__(self, G):
        # задаем начальный символ
        self.G_primary = Grammar(f"{G.start}' -> {G.start}\n{G.grammar_str}")
        # длина самой длинной из продукций
        self.max_G_prime_len = len(max(self.G_primary.grammar, key=len))
        self.G_indexed = []

        # из каждого кортежа ключ-значение из правил
        for head, bodies in self.G_primary.grammar.items():
            for body in bodies:
                # создаем подсписок и в упорядоченном виде добавляем в список правил
                self.G_indexed.append([head, body])

        # согласно грамматике наполняем множества FIRST и FOLLOW
        self.first, self.follow = first_follow(self.G_primary)
        self.all_preceding = self.items(self.G_primary)
        # создаем список возможных действий, причем последний элемент - символ конца входной строки
        self.action = list(self.G_primary.terminals) + ['$']
        # создаем список возможных переходов после reduce на основе списка нетерминалов за исключением стартового
        self.goto = list(self.G_primary.nonterminals - {self.G_primary.start})
        self.parse_table_symbols = self.action + self.goto
        # на основе полученных данных строим таблицу
        self.parse_table = self.construct_table()

    def CLOSURE(self, initial_preceding):
        preceding = initial_preceding

        while True:
            item_len = len(preceding)

            # определяем отношения предшествования
            for head, bodies in preceding.copy().items():
                # для каждой правой части каждой продукции
                for body in bodies.copy():
                    # если есть отношение предшествования
                    if '.' in body[:-1]:
                        symbol_after_dot = body[body.index('.') + 1]
                        # если . предшествует нетерминалу, добавляем closure для этого нетерминала
                        if symbol_after_dot in self.G_primary.nonterminals:
                            for G_body in self.G_primary.grammar[symbol_after_dot]:
                                preceding.setdefault(symbol_after_dot, set()).add(
                                    ('.',) if G_body == ('^',) else ('.',) + G_body)

            # условие выхода из цикла - найдены все варианты отношений
            if item_len == len(preceding):
                return preceding

    def GOTO(self, initial_preceding, symbol):
        # инициализируем пустое множество для совокупности переходов
        goto = {}

        for head, bodies in initial_preceding.items():
            # для каждой правой части продукции
            for body in bodies:
                # если в данной части есть предшествование . символу
                if '.' in body[:-1]:
                    dot_pos = body.index('.')

                    # если символ, следующий за точкой, равен переданному символу
                    if body[dot_pos + 1] == symbol:
                        # переставляем точку и символ
                        replaced_dot_body = body[:dot_pos] + (symbol, '.') + body[dot_pos + 2:]

                        # для точки в новой позиции строится множество closure
                        for C_head, C_bodies in self.CLOSURE({head: {replaced_dot_body}}).items():
                            goto.setdefault(C_head, set()).update(C_bodies)
        return goto

    def items(self, G_prime):
        # изначально точка предшествует стартовому символу
        initial = {G_prime.start: {('.', G_prime.start[:-1])}}
        # вызываем CLOSURE для начального состояния предшествования
        preceding = [self.CLOSURE(initial)]

        while True:
            item_len = len(preceding)
            # для каждого элемента массива предшествующих элементов
            for internal_initial in preceding.copy():
                # для каждого символа грамматики определяются переходы
                for symbol in G_prime.symbols:
                    goto = self.GOTO(internal_initial, symbol)

                    # если переходы найдены и они еще не были добавлены - добавляем их к списку preceding
                    if goto and goto not in preceding:
                        preceding.append(goto)
            # если новых переходов не добавлено - происходит выход из цикла
            if item_len == len(preceding):
                return preceding

    def construct_table(self):
        parse_table = {r: {c: '' for c in self.parse_table_symbols} for r in range(len(self.all_preceding))}

        for i, preceding in enumerate(self.all_preceding):
            for head, bodies in preceding.items():
                for body in bodies:
                    # если в правой части продукции есть точка и она не последний символ
                    if '.' in body[:-1]:  # CASE 2 a
                        symbol_after_dot = body[body.index('.') + 1]

                        # если символ после точки - терминальный
                        if symbol_after_dot in self.G_primary.terminals:
                            # Определяем переход
                            state_goto = self.GOTO(preceding, symbol_after_dot)
                            # находим индекс конкретного перехода
                            target_state = self.all_preceding.index(state_goto)
                            # формируем команду сдвига и перехода в конкретное состояние
                            s = f's{target_state}'
                            # если такой команды в заданном месте нет
                            if s not in parse_table[i][symbol_after_dot]:
                                # и в заданном месте есть команда свертки
                                if 'r' in parse_table[i][symbol_after_dot]:
                                    parse_table[i][symbol_after_dot] += '/'

                                parse_table[i][symbol_after_dot] += s

                    elif body[-1] == '.' and head != self.G_primary.start:  # CASE 2 b
                        for j, (G_head, G_body) in enumerate(self.G_indexed):
                            if G_head == head and (G_body == body[:-1] or G_body == ('^',) and body == ('.',)):
                                for f in self.follow[head]:
                                    if parse_table[i][f]:
                                        parse_table[i][f] += '/'
                                    parse_table[i][f] += f'r{j}'
                                break
                    else:  # CASE 2 c
                        parse_table[i]['$'] = 'acc'
            for A in self.G_primary.nonterminals:  # CASE 3
                j = self.GOTO(preceding, A)
                if j in self.all_preceding:
                    parse_table[i][A] = self.all_preceding.index(j)
        return parse_table

    def print_info(self):
        def fprint(text, variable):
            print(f'{text:>12}: {", ".join(variable)}')

        def print_line():
            print(f'+{("-" * width + "+") * (len(list(self.G_primary.symbols) + ["$"]))}')

        def symbols_width(symbols):
            return (width + 1) * len(symbols) - 1

        print('AUGMENTED GRAMMAR:')

        for i, (head, body) in enumerate(self.G_indexed):
            print(f'{i:>{len(str(len(self.G_indexed) - 1))}}: {head:>{self.max_G_prime_len}} -> {" ".join(body)}')

        print()
        fprint('TERMINALS', self.G_primary.terminals)
        fprint('NONTERMINALS', self.G_primary.nonterminals)
        fprint('SYMBOLS', self.G_primary.symbols)

        print('\nFIRST:')
        for head in self.G_primary.grammar:
            print(f'{head:>{self.max_G_prime_len}} = {{ {", ".join(self.first[head])} }}')

        print('\nFOLLOW:')
        for head in self.G_primary.grammar:
            print(f'{head:>{self.max_G_prime_len}} = {{ {", ".join(self.follow[head])} }}')

        width = max(len(c) for c in {'ACTION'} | self.G_primary.symbols) + 2
        for r in range(len(self.all_preceding)):
            max_len = max(len(str(c)) for c in self.parse_table[r].values())

            if width < max_len + 2:
                width = max_len + 2

        print('\nPARSING TABLE:')
        print(f'+{"-" * width}+{"-" * symbols_width(self.action)}+{"-" * symbols_width(self.goto)}+')
        print(f'|{"":{width}}|{"ACTION":^{symbols_width(self.action)}}|{"GOTO":^{symbols_width(self.goto)}}|')
        print(f'|{"STATE":^{width}}+{("-" * width + "+") * len(self.parse_table_symbols)}')
        print(f'|{"":^{width}}|', end=' ')

        for symbol in self.parse_table_symbols:
            print(f'{symbol:^{width - 1}}|', end=' ')

        print()
        print_line()

        for r in range(len(self.all_preceding)):
            print(f'|{r:^{width}}|', end=' ')

            for c in self.parse_table_symbols:
                print(f'{self.parse_table[r][c]:^{width - 1}}|', end=' ')

            print()

        print_line()
        print()

    def LR_parser(self, w):
        buffer = f'{w} $'.split()
        pointer = 0
        a = buffer[pointer]
        stack = ['0']
        symbols = ['']
        results = {'step': [''], 'stack': ['STACK'] + stack, 'symbols': ['SYMBOLS'] + symbols, 'input': ['INPUT'],
                   'action': ['ACTION']}

        step = 0
        while True:
            s = int(stack[-1])
            step += 1
            results['step'].append(f'({step})')
            results['input'].append(' '.join(buffer[pointer:]))

            if a not in self.parse_table[s]:
                results['action'].append(f'ERROR: unrecognized symbol {a}')

                break

            elif not self.parse_table[s][a]:
                results['action'].append('ERROR: input cannot be parsed by given grammar')

                break

            elif '/' in self.parse_table[s][a]:
                action = 'reduce' if self.parse_table[s][a].count('r') > 1 else 'shift'
                results['action'].append(f'ERROR: {action}-reduce conflict at state {s}, symbol {a}')

                break

            elif self.parse_table[s][a].startswith('s'):
                results['action'].append('shift')
                stack.append(self.parse_table[s][a][1:])
                symbols.append(a)
                results['stack'].append(' '.join(stack))
                results['symbols'].append(' '.join(symbols))
                pointer += 1
                a = buffer[pointer]

            elif self.parse_table[s][a].startswith('r'):
                head, body = self.G_indexed[int(self.parse_table[s][a][1:])]
                results['action'].append(f'reduce by {head} -> {" ".join(body)}')

                if body != ('^',):
                    stack = stack[:-len(body)]
                    symbols = symbols[:-len(body)]

                stack.append(str(self.parse_table[int(stack[-1])][head]))
                symbols.append(head)
                results['stack'].append(' '.join(stack))
                results['symbols'].append(' '.join(symbols))

            elif self.parse_table[s][a] == 'acc':
                results['action'].append('accept')

                break

        return results

    def print_LR_parser(self, results):
        def print_line():
            print(f'{"".join(["+" + ("-" * (max_len + 2)) for max_len in max_lens.values()])}+')

        max_lens = {key: max(len(value) for value in results[key]) for key in results}
        justs = {'step': '>', 'stack': '', 'symbols': '', 'input': '>', 'action': ''}

        print_line()
        print(''.join(
            [f'| {history[0]:^{max_len}} ' for history, max_len in zip(results.values(), max_lens.values())]) + '|')
        print_line()
        for i, step in enumerate(results['step'][:-1], 1):
            print(''.join([f'| {history[i]:{just}{max_len}} ' for history, just, max_len in
                           zip(results.values(), justs.values(), max_lens.values())]) + '|')

        print_line()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('grammar_file', type=argparse.FileType('r'), help='text file to be used as grammar')
    parser.add_argument('tokens', help='tokens to be parsed - all tokens are separated with spaces')
    args = parser.parse_args()

    G = Grammar(args.grammar_file.read())
    slr_parser = SLRParser(G)
    slr_parser.print_info()
    results = slr_parser.LR_parser(args.tokens)
    slr_parser.print_LR_parser(results)


if __name__ == "__main__":
    main()
