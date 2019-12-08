from docassemble.base.util import DAObject, DAList



class Interview(object):
    issue_var = 'issue_var'
    review_edit_button_text = 'Change'
    css_file_name = 'interview_constructor.css'

    def __init__(self, results=None, preferred_result=None):
        self.results = results
        self.preferred_result = preferred_result
        self._interview_logic = None

    @property
    def interview_logic(self):
        return self._interview_logic

    @interview_logic.setter
    def interview_logic(self, logic_piece):
        self._interview_logic = logic_piece
        logic_piece.interview = self
        self.determine_Q_order_and_vars()

    def questions(self, **filters):
        questions = self._interview_logic.questions
        if 'Q_depth' in filters:
            questions = [Q for Q in questions if Q.Q_depth == filters['Q_depth']]
        return questions

    def determine_Q_order_and_vars(self):
        new_Q_list = []
        if len(self.questions(Q_depth=0)) < 1:
            raise RecursionError("Couldn't find any top-level questions.")
        while len(new_Q_list) < len(self.questions()):
            self.Q_iterate(self.questions(Q_depth=0), new_Q_list)

    def Q_iterate(self, Q_list, new_Q_list, Q_num_prefix=''):
        for i, Q in enumerate(Q_list):
            Q.num = Q_num_prefix + str(i + 1)
            Q.var = 'q' + Q.num
            new_Q_list.append(Q)
            if len(Q.sub_Qs) > 0:
                self.Q_iterate(Q.sub_Qs, new_Q_list, Q_num_prefix=Q.num + '_')

    @property
    def result_text(self):
        result_code = ''
        for r, r_text in self.results.items():
            if self.preferred_result is not None:
                span_class = "preferred" if r == self.preferred_result else "non-preferred"
                r_text = '<span class="{0}">{1}</span>'.format(span_class, r_text)
            if result_code == '':
                if_word = 'if'
            else:
                if_word = 'elif'
            result_code += (
                '% {0} {1} is {2}:\n'
                '{3}\n'.format(if_word, Interview.issue_var, r, r_text)
            )
        result_code += '% endif\n'
        result_code_literal_unicode = literal_unicode(result_code)
        return result_code_literal_unicode

    def return_dict(self):
        interview_dict = []

        # Append the initial block, for sections:
        interview_dict.append({
            'sections': [{'Questions': []}, 'Determination'],
            'features': {
                'navigation': True,
                'css': Interview.css_file_name
            }
        })
        # Append the main issue code block:
        interview_dict.append({
            'code': literal_unicode(
                'if {0}:\n'
                '  {1} = True\n'
                'else:\n'
                '  {1} = False\n'.format(self.interview_logic.logic, Interview.issue_var)
            )
        })
        # Append the mandatory code block:
        interview_dict.append({
            'mandatory': True,
            'code': literal_unicode(
                '{0}\n'
                'answers_reviewed\n'.format(Interview.issue_var)
            )
        })
        # Create the review list:
        review_list = [
            {'note': self.result_text},
            {'note': literal_unicode(u"Here's what you answered:\n")}
        ]
        # Append the review block:
        review_block = {
            'section': 'Determination',
            'question': literal_unicode(u"What we've determined\n"),
            'review': review_list,
            'field': 'answers_reviewed'
        }
        interview_dict.append(review_block)
        # Append all the questions, etc:
        self.get_yml_for_questions(self.questions(), interview_dict, review_list)

        return interview_dict

    def get_yml_for_questions(self, question_list, interview_dict, review_list):
        for i, Q in enumerate(question_list):
            # Basic:
            interview_dict.append(Q.get_Q_dict())
            review_list.append(Q.get_review_list_entry())
            # Add sections (for base questions only):
            if Q.Q_depth is 0:
                interview_dict[0]['sections'][0]['Questions'].append('Question ' + Q.num)

    def write_yml(self):
        with open('output.yml', 'w') as yml_file:
            yaml.dump_all(self.return_dict(), yml_file)


class LogicPiece(DAObject):
    def __init__(self, *args, instance_name=None):
        if instance_name is not None:
            super().__init__(instance_name)
        else:
            super().__init__()
      
        self.args = args
        self.bool = True
        self.interview = None

        self.parent = None
        self.children = []
        for arg in args:
            self.children.append(arg)
            arg.parent = self

    def ancestors(self, class_filter=None):
        ancestors = []
        if self.parent is not None:
            ancestors.append(self.parent)
            ancestors.extend(self.parent.ancestors())
        if class_filter is not None:
            ancestors = [a for a in ancestors if isinstance(a, class_filter)]
        return ancestors

    def descendants(self, class_filter=None):
        descendants = []
        for child in self.children:
            descendants.append(child)
            descendants.extend(child.descendants())
        if class_filter is not None:
            descendants = [d for d in descendants if isinstance(d, class_filter)]
        return descendants

    @property
    def questions(self):
        Q_descendants = [d for d in self.descendants() if isinstance(d, Question)]
        return Q_descendants

    @property
    def bool_effect(self):
        """Returns the effect on the interview issue
                        Can be True or False:
                        True -> If this question is answered 'Yes',
                            it helps the issue result be 'Yes'
                        False -> A 'Yes' to this question pushes toward
                            'No' for the issue result (and vice versa)
                        """
        effect = True
        for anc in self.ancestors():
            effect = effect and anc.bool
        return effect
            
            
class NOT(LogicPiece):
    def __init__(self, arg):
        super().__init__(arg)
        self.arg = arg
        self.bool = False

    @property
    def logic(self):
        if isinstance(self.arg, Question):
            logic_str = self.arg.logic
            if logic_str.endswith('True'):
                logic_str = logic_str[:-4] + 'False'
            elif logic_str.endswith('False'):
                logic_str = logic_str[:-5] + 'True'
        else:
            logic_str = 'not ' + self.arg.logic
        return logic_str


class AND(LogicPiece):
    @property
    def logic(self):
        arg_logics = [arg.logic for arg in self.args]
        logic_str = '(' + ' and '.join(arg_logics) + ')'
        return logic_str


class OR(LogicPiece):
    @property
    def logic(self):
        arg_logics = [arg.logic for arg in self.args]
        logic_str = '(' + ' or '.join(arg_logics) + ')'
        return logic_str


class OR_SUB(OR):
    def __init__(self, super_Q, sub_logic_piece):
        super().__init__(super_Q, sub_logic_piece)
        self.super_Q = super_Q
        self.sub_logic_piece = sub_logic_piece
        super_Q.is_super_Q = True
        super_Q.sub_logic_piece = sub_logic_piece
        super_Q.sub_Qs = sub_logic_piece.questions
        sub_logic_piece.super_Q = super_Q

    @property
    def logic(self):
        logic_str = '({0} or ({1}.answer is None and {2}))'.format(
            self.super_Q.logic, self.super_Q.var, self.sub_logic_piece.logic
        )
        return logic_str


class Question(LogicPiece):
    def __init__(self, instance_name, Q_text, answers=None, q_type='buttons'):
        super().__init__(instance_name=instance_name)
        self.var = instance_name
        self.Q_text = Q_text
        self.answers = answers
        self.type = q_type

        # Sub-questions:
        self.is_super_Q = False
        self.sub_logic_piece = None
        self.sub_Qs = []
        
    @property
    def logic(self):
        if self.var is not None:
            return self.var + '.answer is True'

    @property
    def questions(self):
        return [self]

    @property
    def Q_depth(self):
        """
        :returns int, giving this question's depth
        0 -> top-level questions
        1 -> sub-question to a top-level question
        etc...
        """
        depth = 0
        ancestors = self.ancestors()
        for a in ancestors:
            if isinstance(a, OR_SUB) and (a.sub_logic_piece is self or a.sub_logic_piece in ancestors):
                depth += 1
        return depth

    def get_Q_dict(self):
        Q_dict = {
            'section': 'Question ' + re.search(r'^[^_]+', self.num).group(),
            'question': literal_unicode(self.text + '\n')
        }
        if self.type == 'buttons':
            if len(self.sub_Qs) == 0:
                Q_dict['yesno'] = self.var
            elif len(self.sub_Qs) > 0:
                Q_dict['yesnomaybe'] = self.var
        elif self.type == 'radio':
            if len(self.sub_Qs) == 0:
                Q_dict['fields'] = {
                    'no label': self.var,
                    'datatype': 'yesnoradio'
                }
            elif len(self.sub_Qs) > 0:
                Q_dict['fields'] = {
                    'no label': self.var,
                    'datatype': 'yesnomaybe'
                }
        return Q_dict

    def get_review_list_entry(self):
        review_list_entry = {
            Interview.review_edit_button_text: [
                self.var,
                {'recompute': [Interview.issue_var]}
                # Could add option here, to undefine subQ answers if super_Q is answered
            ],
            'button': self.review_button_element()
        }
        show_if_list = self.show_if_list()
        if len(show_if_list) > 0:
            review_list_entry['show if'] = show_if_list
        return review_list_entry

    def review_button_element(self):
        indent = self.Q_depth * 30
        # review_button = literal_unicode(
        #     '<span style="text-indent: {0}px;">{1}'
        #     '</span>\n'.format(indent, self.review_button_text)
        # )
        review_button = literal_unicode(
            '<ul class="review-button">\n'
            '<li style="text-indent: {0}px;">{1}'
            '</li>\n'
            '</ul>\n'.format(indent, self.review_button_text())
        )
        return review_button

    def review_button_text(self):
        review_button_text = '\\\n'
        # For super-questions, the review button text uses the OR_SUB's logic:
        if self.is_super_Q is True:
            review_button_text += (
                '% if {0}:\n'
                '{1}\n'
                '% else:\n'
                '{2}\n'
                '% endif\n'.format(self.parent.logic, self.answers[True], self.answers[False])
            )
        else:
            for a, a_text in self.answers.items():
                # if self.preferred_answer is not None:
                #     # span_class = "preferred" if a == self.preferred_answer else "non-preferred"
                #     a_text = '<span class="{0}">{1}</span>'.format(span_class, a_text)
                if review_button_text is '\\\n':
                    if_word = 'if'
                else:
                    if_word = 'elif'
                review_button_text += (
                    '% {0} {1} is {2}:\n'
                    '{3}\n'.format(if_word, self.var, a, a_text)
                )
            review_button_text += '% endif\n'
        review_button_text_literal_unicode = literal_unicode(review_button_text)
        return review_button_text_literal_unicode

    def show_if_list(self):
        show_if_list = []
        ancestors = self.ancestors()
        for a in ancestors:
            if isinstance(a, OR_SUB) and (a.sub_logic_piece is self or a.sub_logic_piece in ancestors):
                entry = '{0} is None'.format(a.super_Q.var)
                show_if_list.append(entry)
        return show_if_list


