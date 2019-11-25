import yaml
from numpy import unicode
import re


# READING:
# with open('output.yml') as file:
#     # The FullLoader parameter handles the conversion from YAML
#     # scalar values to Python the dictionary format
#     documents = yaml.load_all(file, Loader=yaml.FullLoader)
#
#     print(documents)
#
#     for doc in documents:
#         print(doc)





# WRITING:
class literal_unicode(unicode): pass

def literal_unicode_representer(dumper, data):
    return dumper.represent_scalar(u'tag:yaml.org,2002:str', data, style='|')

yaml.add_representer(literal_unicode, literal_unicode_representer)


class Interview(object):
    def __init__(self, results=None, preferred_result=None, Q_logic=None):
        self.questions = []
        self.issue_var = 'issue_liable'
        self.review_label = 'Change'

        self.results = results
        self.preferred_result = preferred_result

        self.relationships = []
        self._Q_logic = Q_logic

    def write_yml(self):
        with open('output.yml', 'w') as yml_file:
            yaml.dump_all(self.return_dict(), yml_file)

    def determine_Q_order_and_vars(self):
        new_Q_list = []
        top_level_Qs = []
        for q in self.questions:
            if q.super_Q is None:
                top_level_Qs.append(q)
        if len(top_level_Qs) < 1:
            raise RecursionError("Couldn't find any top-level questions.")
        while(len(new_Q_list) < len(self.questions)):
            self.Q_iterate(top_level_Qs, new_Q_list)
        self.questions = new_Q_list

    def Q_iterate(self, Q_list, new_Q_list, q_num_prefix=''):
        for i, q in enumerate(Q_list):
            q.num = q_num_prefix + str(i + 1)
            q.var = 'q' + q.num
            new_Q_list.append(q)
            if len(q.sub_Qs) > 0:
                self.Q_iterate(q.sub_Qs, new_Q_list, q_num_prefix=q.num + '_')

    @property
    def Q_logic(self):
        if self._Q_logic:
            return self._Q_logic
        else:
            Q_logic = " and ".join([q.var for q in self.questions if q.super_Q is None])
            return Q_logic

    @Q_logic.setter
    def Q_logic(self, Q_logic):
        self._Q_logic = Q_logic

    @property
    def result_text(self):
        result_code = ''
        for r, r_text in self.results.items():
            if self.preferred_result:
                span_class = "preferred" if r == self.preferred_result else "non-preferred"
                r_text = '<span class="{0}">{1}</span>'.format(span_class, r_text)
            if result_code == '':
                if_word = 'if'
            else:
                if_word = 'elif'
            result_code += (
                '% {0} {1} == {2}:\n'
                '{3}\n'.format(if_word, self.issue_var, r, r_text)
            )
        result_code += '% endif\n'
        result_code_literal_unicode = literal_unicode(result_code)
        return result_code_literal_unicode

    def return_dict(self):
        interview_dict = []

        # Append the initial block, for sections:
        interview_dict.append({
            'sections': [{'Questions': []}, 'Determination'],
            'features': {'navigation': True}
        })
        # Append the main issue code block:
        interview_dict.append({
            'code': literal_unicode(
                'if {0}:\n'
                '  {1} = True\n'
                'else:\n'
                '  {1} = False\n'.format(self.Q_logic, self.issue_var)
            )
        })
        # Append the mandatory code block:
        interview_dict.append({
            'mandatory': True,
            'code': literal_unicode(
                '{0}\n'
                'answers_reviewed\n'.format(self.issue_var)
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
            'field': 'answers_reviewed',
            'css': literal_unicode(
                '<style>\n'
                '  .preferred {\n'
                '    color: green;\n'
                '  }\n'
                '  .non-preferred {\n'
                '    color: red;\n'
                '  }\n'
                '</style>\n'
            )
        }
        interview_dict.append(review_block)
        # Append all the questions, etc:
        self.write_yml_for_questions(self.questions, interview_dict, review_list)

        return interview_dict

    def write_yml_for_questions(self, question_list, interview_dict, review_list):
        for i, q in enumerate(question_list):
            # Basic:
            q_dict = q.get_q_dict()
            interview_dict.append(q_dict)
            # Add sections (for base questions only):
            if re.match(r'^\d+$', q.num):
                interview_dict[0]['sections'][0]['Questions'].append('Question ' + q.num)
            # Append to the review list:
            review_list_entry = {
                self.review_label: [q.var_for_review_list, {'recompute': q.recompute_list}],
                'button': q.get_review_button()
            }
            review_list.append(review_list_entry)
            if len(q.show_if_list) > 0:
                review_list_entry['show if'] = q.show_if_list
            if len(q.sub_Qs) > 0:
                code_block = q.get_code_block_for_q_with_subQs()
                interview_dict.append(code_block)

    def add_questions(self, *questions):
        for q in questions:
            q.interview = self
            if q in self.questions:
                continue
            self.questions.append(q)
        self.determine_Q_order_and_vars()

    def set_interview_logic(self, bool, *questions):
        new_relationship = (bool, *questions)
        self.relationships.append(new_relationship)




class Question(object):
    def __init__(self, q_text, q_review_text_true="Yes",
                 q_review_text_false="No", q_type='buttons', sub_Q_logic=None):
        self.var = None
        self.num = None
        self.text = q_text
        self.review_text_true = q_review_text_true
        self.review_text_false = q_review_text_false
        self.type = q_type
        self.super_Q = None
        self.sub_Qs = []
        self._sub_Q_logic = sub_Q_logic
        self.interview = None
        self._dependent_Qs = []
        self._dependent_on = []

    @property
    def var_for_review_list(self):
        if len(self.sub_Qs) > 0:
            return self.var + '_A'
        elif len(self.sub_Qs) == 0:
            return self.var

    @property
    def recompute_list(self):
        """The recompute_list dictates what variables
        must be recomputed (i.e. asked again) when
        the user clicks "Change" for this question
        on the review page."""
        recompute_list = []
        if len(self.sub_Qs) > 0:
            recompute_list.append(self.var)
        recompute_list.extend(self.get_super_Q_recompute_vars())
        # Always recompute the issue_var:
        recompute_list.append(self.interview.issue_var)
        return recompute_list

    def get_super_Q_recompute_vars(self):
        super_Q_recompute_vars = []
        if self.super_Q is not None:
            super_Q_recompute_vars = self.super_Q.get_super_Q_recompute_vars()
            super_Q_recompute_vars.insert(0, self.super_Q.var)
        return super_Q_recompute_vars

    def get_all_super_Qs(self):
        all_super_Qs = []
        if self.super_Q is not None:
            all_super_Qs.extend(self.super_Q.get_all_super_Qs())
            all_super_Qs.append(self.super_Q)
        return all_super_Qs

    @property
    def show_if_list(self):
        """The show_if_list dictates the conditions
        for this question to appear on the review page."""
        show_if_list = []
        for q_depended_on, bool in self.dependent_on:
            show_if_list.append('{0} == {1}'.format(q_depended_on.var, bool))
        for super_Q in self.get_all_super_Qs():
            show_if_list.append('{0} == None'.format(super_Q.var_for_review_list))
        return show_if_list

    def add_sub_Qs(self, *sub_Qs):
        for sub_Q in sub_Qs:
            if sub_Q is self:
                raise SyntaxError("A question cannot be its own sub-question")
            if sub_Q not in self.sub_Qs:
                self.sub_Qs.append(sub_Q)
            if self is not sub_Q.super_Q:
                sub_Q.super_Q = self
        if self.interview is not None:
            self.interview.determine_Q_order_and_vars()

    @property
    def dependent_Qs(self):
        dependent_Qs = [dq for dq in self._dependent_Qs if dq in self.interview.questions]
        return dependent_Qs

    @property
    def dependent_on(self):
        dependent_on = [dq for dq in self._dependent_on if dq in self.interview.questions]
        return dependent_on

    def set_dependent_Qs(self, bool, *dependent_Qs):
        for q in dependent_Qs:
            self._dependent_Qs.append((q, bool))
            q._dependent_on.append((self, bool))

    @property
    def dependencies_satisfied(self, question_list):
        for dq in self.dependent_on:
            if dq not in self.interview.questions:
                continue
            if dq not in question_list:
                return False
        return True

    def get_q_dict(self):
        q_dict = {
            'section': 'Question ' + re.search(r'^[^_]+', self.num).group(),
            'question': literal_unicode(self.text + "\n")
        }
        if self.type == 'buttons':
            if len(self.sub_Qs) == 0:
                q_dict['yesno'] = self.var
            elif len(self.sub_Qs) > 0:
                q_dict['yesnomaybe'] = self.var + '_A'
        elif self.type == 'radio':
            if len(self.sub_Qs) == 0:
                q_dict['fields'] = {
                    'no label': self.var,
                    'datatype': 'yesnoradio'
                }
            elif len(self.sub_Qs) > 0:
                q_dict['fields'] = {
                    'no label': self.var + '_A',
                    'datatype': 'yesnomaybe'
                }
        return q_dict

    @property
    def sub_Q_logic(self):
        if self._sub_Q_logic:
            return self._sub_Q_logic
        else:
            sub_Q_logic = " and ".join([q.var for q in self.sub_Qs])
            return sub_Q_logic

    @sub_Q_logic.setter
    def sub_Q_logic(self, sub_Q_logic):
        self._sub_Q_logic = sub_Q_logic

    def get_code_block_for_q_with_subQs(self):
        code_block = {
            'code': literal_unicode(
                'if {0} == True:\n'
                '  {1} = True\n'
                'elif {0} == False:\n'
                '  {1} = False\n'
                'elif {2}:\n'
                '  {1} = True\n'
                'else:\n'
                '  {1} = False\n'.format(self.var_for_review_list, self.var, self.sub_Q_logic)
            )
        }
        return code_block

    @property
    def q_depth(self):
        if self.super_Q:
            return self.super_Q.q_depth + 1
        else:
            return 0

    def get_review_button(self):
        indent = self.q_depth * 30
        review_button = literal_unicode(
            '<ul>\n'
            '<li style="text-indent: {0}px;">{1}'
            '</li>\n'
            '</ul>\n'.format(indent, self.review_button_text)
        )
        return review_button

    @property
    def review_button_text(self):
        text = (
            # 'Question {0}: \\\n'
            '\\\n'
            '% if {0}:\n'
            '{1}\\\n'
            '% else:\n'
            '{2}\\\n'
            '% endif\n'.format(self.var, self.review_text_true, self.review_text_false)
        )
        return text



# EXAMPLE 1: APPLE PIE INTERVIEW
test_interview1 = Interview(
    results={
        True: "You would like apple pie!",
        False: "You wouldn't like apple pie, I'm afraid."
    },
    preferred_result=True
)
q1 = Question('Do you like pie?')
q2 = Question('Do you like apples?')
q2_1 = Question("Hmm, you don't know! Well do you usually like fruits?")
q2_2 = Question("And do you usually like spherical fruits?")
q2_2_1 = Question("Do you usually like round fruits?")
test_interview1.add_questions(q1, q2, q2_1, q2_2, q2_2_1)
q2.add_sub_Qs(q2_1, q2_2)
q2_2.add_sub_Qs(q2_2_1)


# EXAMPLE 2: TENANT REPAIR INTERVIEW
test_interview2 = Interview(
    results={
        True: "You do *not* have to pay for the repair.",
        False: "You have to pay for the repair."
    },
    preferred_result=True
)
q1 = Question(
    q_text='Is the broken item a part of the apartment?',
    q_review_text_true='The broken item is a part of the apartment.',
    q_review_text_false='The broken item is not a part of the apartment.'
)
q2 = Question(
    q_text='Did you cause the damage to the broken item?',
    q_review_text_true='You caused the damage to the broken item.',
    q_review_text_false="You didn't cause the damage to the broken item."
)
q3 = Question(
    q_text='Did you **intend** to break the item?',
    q_review_text_true='You intended to break the item.',
    q_review_text_false="You didn't intend to break the item."
)
q4 = Question(
    q_text='Were you being negligent or careless when you broke the item?',
    q_review_text_true="You were negligent.",
    q_review_text_false="You weren't negligent."
)

test_interview2.add_questions(q1, q2, q3, q4)
test_interview2.Q_logic = "q1 and (not q2 or (not q3 and not q4))"

q1.set_dependent_Qs(True, q2)
q3.set_dependent_Qs(False, q4)






test_interview1.write_yml()



