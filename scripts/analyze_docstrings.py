import sys
import csv
import re
import inspect
import pandas
from numpydoc.docscrape import NumpyDocString


class Docstring:
    def __init__(self, class_, method_name, method_obj):
        self.class_ = class_
        self.method_name = method_name
        self.method_obj = method_obj
        self.raw_doc = method_obj.__doc__ or ''
        self.doc = NumpyDocString(self.raw_doc)

    def __len__(self):
        return len(self.raw_doc)

    @property
    def first_line_blank(self):
        if self.raw_doc:
            return not bool(self.raw_doc.split('\n')[0].strip())

    @property
    def summary(self):
        return ' '.join(self.doc['Summary'])

    @property
    def extended_summary(self):
        return ' '.join(self.doc['Extended Summary'])

    @property
    def needs_summary(self):
        return not (bool(self.summary) and bool(self.extended_summary))

    @property
    def doc_parameters(self):
        return self.doc['Parameters']

    @property
    def signature_parameters(self):
        params = tuple(inspect.signature(self.method_obj).parameters.keys())
        return params[1:] if params and params[0] in ('self', 'cls') else params

    @property
    def correct_parameters(self):
        if self.doc_parameters:
            doc_param_names = list(zip(*self.doc_parameters))[0]
            return doc_param_names == self.signature_parameters

        return not bool(self.signature_parameters)

    @property
    def see_also(self):
        return self.doc['See Also']

    @property
    def examples(self):
        return self.doc['Examples']

    @property
    def first_line_ends_in_dot(self):
        if self.doc:
            return self.doc.split('\n')[0][-1] == '.'

    @property
    def deprecated(self):
        pattern = re.compile('.. deprecated:: ')
        return (bool(pattern.search(self.summary)) or
                bool(pattern.search(self.extended_summary)))


def main():
    writer = csv.writer(sys.stdout)
    writer.writerow(['Class',
                     'Method',
                     'Is deprecated',
                     'Missing short or long summary',
                     'Missing, incomplete or wrong parameters',
                     'Needs examples',])
    for class_ in [pandas.Series, pandas.DataFrame]:
        for method_name, method_obj in inspect.getmembers(class_):
            if callable(method_obj) and method_name[0] != '_':
                doc = Docstring(class_, method_name, method_obj)
                writer.writerow([doc.class_.__name__,
                                 doc.method_name,
                                 int(doc.deprecated),
                                 int(doc.needs_summary),
                                 int(not doc.correct_parameters),
                                 int(not bool(doc.examples))])


if __name__ == '__main__':
    main()
