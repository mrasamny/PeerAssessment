#!/usr/bin/env python3

import csv
import argparse
import io
from pathlib import Path
import sys
import zipfile

def get_groups(csv_filename):
    is_header = True
    groups = {}
    with open(csv_filename, newline='') as csvfile:
        group_reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        for row in group_reader:
            if is_header:
                is_header = False
                continue              
            group_name = row[5].strip()
            if not group_name:
                print(f'Skipping unassigned student: {row[0]}', file=sys.stderr)
                continue
            raw_name = row[0].title().split(" ") # Canvas member name
            student_name = raw_name[-1] + " " + ' '.join(raw_name[:-1])
            if group_name in groups:
                groups[group_name].append(student_name)
            else:
                groups[group_name] = [student_name]
    return groups


def get_rubric(rubric_filename):
    rubric = []
    with open(rubric_filename, newline='') as rubricfile:
        rubric_reader = csv.reader(rubricfile, delimiter=',', quotechar='"')
        for row in rubric_reader:
            html = f'<p>{row[0]}</p><ol>'
            index = 1
            while index < len(row):
                html += f'<li>{row[index]}</li>'
                index += 1
            html += '</ol>'
            rubric.append(html)

    return rubric


def generate_survey(rubric, groups):
    survey = {}
    for group, members in groups.items():
        survey[group] = []

    for category in rubric:
        for group, students in groups.items():
            for student in students:
                question = category
                question += f'<p>Rate <span style="color:green;font-weight:bold;">{student}</span> using the rubric above.</p>'
                survey[group].append(question)
    return survey


def create_txt_file(groups, survey, no_fire=False):
    for group, questions in survey.items():
        with open(group+'_survey.txt', 'w', newline='') as txt_file:
            for question in questions:
                print('MC', question, 1, 'correct', 2, 'incorrect', 3, 'incorrect', 4, 'incorrect', 5, 'incorrect',
                      sep='\t', file=txt_file)
            if not no_fire:
                ma_choices = ''
                for student in groups[group]:
                    ma_choices += '\t' + student + '\t' + 'incorrect'
                print('MA', 'Select members you recommend for firing.'+ma_choices, sep='\t', file=txt_file)

def create_markdown_file(groups, survey, output_dir=Path('.'), no_fire=False):
    output_dir.mkdir(parents=True, exist_ok=True)
    for group, questions in survey.items():
        with open(output_dir / f'{group}_survey.txt', 'w', newline='') as txt_file:
            q_number = 1
            for question in questions:
                print(f'{q_number}. {question}', file=txt_file)
                print(f'*A) 1', file=txt_file)
                print(f'B) 2', file=txt_file)
                print(f'C) 3', file=txt_file)
                print(f'D) 4', file=txt_file)
                print(f'E) 5', file=txt_file)
                print(file=txt_file)
                q_number += 1

            if not no_fire:
                print(f'{len(questions) + 1}. Select members you recommend for firing.', file=txt_file)
                for student in groups[group]:
                    print('[*]', student, file=txt_file)


def create_surveys(project_csv, rubric_csv, output_dir, qti=False, no_fire=False):
    project_csv = Path(project_csv).expanduser()
    rubric_csv = Path(rubric_csv).expanduser()
    output_dir = Path(output_dir).expanduser()
    for label, path in (('Project CSV', project_csv), ('Rubric CSV', rubric_csv)):
        if not path.is_file():
            raise FileNotFoundError(f'{label} not found: {path}')

    groups = get_groups(project_csv)
    rubric = get_rubric(rubric_csv)
    if not groups:
        raise ValueError('The project CSV contains no assigned groups.')
    if not rubric:
        raise ValueError('The rubric CSV contains no questions.')
    survey = generate_survey(rubric, groups)
    if qti:
        create_qti_files(groups, survey, output_dir, no_fire=no_fire)
    else:
        create_markdown_file(groups, survey, output_dir, no_fire=no_fire)
    return len(groups)


def launch_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title('Create Peer Assessment Surveys')
    root.resizable(True, False)
    frame = ttk.Frame(root, padding=18)
    frame.grid(sticky='nsew')
    frame.columnconfigure(1, weight=1)
    root.columnconfigure(0, weight=1)

    project = tk.StringVar()
    rubric = tk.StringVar()
    output = tk.StringVar()
    qti = tk.BooleanVar(value=False)
    no_fire = tk.BooleanVar(value=False)
    output_changed = False

    def choose_csv(target):
        nonlocal output_changed
        filename = filedialog.askopenfilename(
            parent=root, title='Select CSV file', filetypes=[('CSV files', '*.csv'), ('All files', '*.*')])
        if filename:
            target.set(filename)
            if target is project and not output_changed:
                output.set(str(Path(filename).parent))

    def choose_output():
        nonlocal output_changed
        directory = filedialog.askdirectory(parent=root, title='Select output folder',
                                            initialdir=output.get() or str(Path.home()))
        if directory:
            output.set(directory)
            output_changed = True

    ttk.Label(frame, text='Select the project CSV and output folder. The rubric defaults to rubric.csv beside the project CSV.').grid(
        row=0, column=0, columnspan=3, sticky='w', pady=(0, 12))
    fields = [
        ('Project / groups CSV', project, lambda: choose_csv(project)),
        ('Rubric CSV (optional)', rubric, lambda: choose_csv(rubric)),
        ('Output folder', output, choose_output),
    ]
    for row, (label, variable, browse) in enumerate(fields, 1):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', padx=(0, 10), pady=5)
        ttk.Entry(frame, textvariable=variable, width=55).grid(row=row, column=1, sticky='ew', pady=5)
        ttk.Button(frame, text='Browse…', command=browse).grid(row=row, column=2, padx=(8, 0), pady=5)

    ttk.Checkbutton(frame, text='Create Canvas QTI ZIP files', variable=qti).grid(
        row=4, column=0, columnspan=3, sticky='w', pady=(10, 2))
    ttk.Checkbutton(frame, text='Omit firing recommendation question', variable=no_fire).grid(
        row=5, column=0, columnspan=3, sticky='w')

    def run():
        if not project.get().strip() or not output.get().strip():
            messagebox.showerror('Missing selection', 'Select a project CSV and an output folder.', parent=root)
            return
        rubric_path = rubric.get().strip() or str(Path(project.get().strip()).expanduser().parent / 'rubric.csv')
        try:
            count = create_surveys(project.get(), rubric_path, output.get(), qti.get(), no_fire.get())
        except (Exception, SystemExit) as exc:
            messagebox.showerror('Could not create surveys', str(exc), parent=root)
            return
        messagebox.showinfo('Surveys created',
                            f'Created surveys for {count} groups in:\n{output.get()}', parent=root)

    ttk.Button(frame, text='Create surveys', command=run).grid(
        row=6, column=0, columnspan=3, sticky='e', pady=(16, 0))
    root.mainloop()


def create_qti_files(groups, survey, output_dir, no_fire=False):
    try:
        from text2qti.config import Config
        from text2qti.quiz import Quiz
        from text2qti.qti import QTI
    except ImportError as exc:
        raise SystemExit('QTI export requires text2qti: python3 -m pip install text2qti') from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    for group, questions in survey.items():
        lines = [f'Quiz title: {group} Peer Assessment',
                 'Show correct answers: false', '']
        for number, question in enumerate(questions, 1):
            lines.extend([f'{number}. {question}', '*A) 1', 'B) 2',
                          'C) 3', 'D) 4', 'E) 5', ''])
        if not no_fire:
            lines.append(f'{len(questions) + 1}. Select members you recommend for firing.')
            lines.extend(f'[*] {student}' for student in groups[group])

        qti = QTI(Quiz('\n'.join(lines) + '\n', config=Config()))
        source = io.BytesIO(qti.zip_bytes())
        output_path = output_dir / f'{group}_survey.zip'
        with zipfile.ZipFile(source) as input_zip, zipfile.ZipFile(
                output_path, 'w', compression=zipfile.ZIP_DEFLATED) as output_zip:
            for member in input_zip.infolist():
                data = input_zip.read(member.filename)
                if member.filename.endswith('/assessment_meta.xml'):
                    data = data.replace(b'<quiz_type>assignment</quiz_type>',
                                        b'<quiz_type>survey</quiz_type>')
                    if b'<quiz_type>survey</quiz_type>' not in data:
                        raise RuntimeError('Could not mark the QTI package as a survey')
                output_zip.writestr(member, data)
        print(output_path)


if __name__=="__main__":
    if len(sys.argv) == 1:
        launch_gui()
        sys.exit(0)
    parser = argparse.ArgumentParser(description='Create peer assessment surveys.')
    parser.add_argument('project_csv', help='Canvas project/group CSV file')
    parser.add_argument('rubric_csv', nargs='?', default='rubric.csv')
    parser.add_argument('--qti', action='store_true',
                        help='create Canvas QTI ZIP packages instead of text files')
    parser.add_argument('--no-fire', action='store_true',
                        help='omit the question recommending members for firing')
    parser.add_argument('--output-dir', type=Path, default=Path('.'))
    args = parser.parse_args()
    create_surveys(args.project_csv, args.rubric_csv, args.output_dir,
                   qti=args.qti, no_fire=args.no_fire)
