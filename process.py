#!/usr/bin/env python3

"""
Summarize a group peer assessment without publishing individual ratings.
This is based on the specific format of the peer assessment survey questions
(see create_survey.py) and the way Canvas writes survey results to CSV files.

Usage:
    python3 process.py <group_assessment_result>.csv
    python3 process.py <group_assessment_result>.csv <project_roster>.csv
"""

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path


QUESTION_PATTERN = re.compile(
    r"^(.+?):.*\bRate\s+(.+?)\s+using the rubric above\.\s*$",
    re.DOTALL,
)


def _name_key(name: str) -> str:
    """Match names despite differences in case, spaces, and punctuation."""
    return re.sub(r"[^\w]", "", name, flags=re.UNICODE).casefold()


def read_project_roster(group_roster_file: str | Path) -> dict[str, list[str]]:
    """Return group names mapped to student names from a Canvas roster CSV."""
    roster: dict[str, list[str]] = {}
    with Path(group_roster_file).open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if not {"name", "group_name"}.issubset(reader.fieldnames or []):
            raise ValueError("Roster must contain name and group_name columns")

        for row in reader:
            group = (row["group_name"] or "").strip()
            raw_name = (row["name"] or "").strip()
            if not group or not raw_name:
                continue
            # Canvas exports the roster as LAST FIRST; questions use First Last.
            parts = raw_name.split()
            student = " ".join(parts[1:] + parts[:1]).title()
            roster.setdefault(group, []).append(student)

    return roster


def summarize_assessment(
    group_roster_file: str | Path, assessment_file: str | Path
) -> dict:
    """Return each student's rating distribution, including self-ratings."""
    roster = read_project_roster(group_roster_file)
    with Path(assessment_file).open(newline="", encoding="utf-8-sig") as file:
        reader = csv.reader(file)
        headers = next(reader, None)
        if not headers or headers[0].strip().casefold() != "name":
            raise ValueError("Assessment must have a Name column in position 1")

        questions = []
        recommended_column = None
        for index, header in enumerate(headers):
            match = QUESTION_PATTERN.search(header.strip())
            if match:
                questions.append((index, match.group(1).strip(), match.group(2).strip()))
            elif header.strip().casefold() == "select members you recommend for firing.":
                recommended_column = index
        if not questions:
            raise ValueError("No rubric questions with rated student names were found")

        respondents: set[str] = set()
        rating_rows: list[tuple[int, list[str]]] = []
        for line_number, row in enumerate(reader, start=2):
            if len(row) != len(headers):
                raise ValueError(f"Assessment row {line_number} has the wrong number of columns")
            respondent = _name_key(row[0].strip())
            if respondent in respondents:
                raise ValueError(f"Assessment row {line_number} repeats a respondent")
            respondents.add(respondent)
            rating_rows.append((line_number, row))

        rated_names = {_name_key(name) for _, _, name in questions}
        matching_groups = [
            group for group, students in roster.items()
            if respondents <= {_name_key(student) for student in students}
            and rated_names & {_name_key(student) for student in students}
        ]
        if len(matching_groups) != 1:
            raise ValueError("Respondents and question names do not identify one roster group")
        group = matching_groups[0]
        group_names = {_name_key(student) for student in roster[group]}

        # Preserve the question order and include roster members without questions.
        student_names = {}
        categories = []
        for _, category, student in questions:
            student_names.setdefault(_name_key(student), student)
            if category not in categories:
                categories.append(category)
        for student in roster[group]:
            student_names.setdefault(_name_key(student), student)

        scores: dict[str, dict[str, list[int]]] = {
            category: {student: [] for student in student_names}
            for category in categories
        }
        recommendations: Counter[str] = Counter()
        for line_number, row in rating_rows:
            for index, category, student in questions:
                answer = row[index].strip()
                if not answer:
                    continue
                if answer not in {"1", "2", "3", "4", "5"}:
                    raise ValueError(f"Assessment row {line_number} has an invalid rating")
                scores[category][_name_key(student)].append(int(answer))
            if recommended_column is not None:
                for name in row[recommended_column].split(","):
                    name = name.strip()
                    if name:
                        key = _name_key(name)
                        if key not in student_names:
                            raise ValueError(
                                f"Assessment row {line_number} recommends an unknown student"
                            )
                        recommendations[key] += 1

    return {
        "group": group,
        "respondent_count": len(respondents),
        "rated_students_not_in_roster": [
            student_names[key] for key in student_names if key in rated_names - group_names
        ],
        "roster_students_not_rated": [
            student_names[key] for key in student_names if key in group_names - rated_names
        ],
        "rubric_summary": {
            category: {
                student_names[key]: {
                    "mean": (
                        sum(values) / len(values)
                        if key in respondents and values
                        else 0.0
                    ),
                    "counts": [values.count(rating) for rating in range(1, 6)],
                }
                for key, values in students.items()
            }
            for category, students in scores.items()
        },
        "recommended_for_firing": {
            student_names[key]: count for key, count in recommendations.items()
        },
    }


def format_summary(summary: dict) -> str:
    """Format the aggregate counts as a readable text report."""
    lines = []
    for category, students in summary["rubric_summary"].items():
        if lines:
            lines.append("")
        lines.extend((category, "-" * len(category)))
        width = max(25, *(len(name) + 2 for name in students))
        for name, ratings in students.items():
            lines.append(
                f"{name:<{width}}\t{ratings['mean']:.2f}\t{ratings['counts']}"
            )

    title = "Recomended for Firing"
    lines.extend(("", title, "-" * len(title)))
    recommendations = summary["recommended_for_firing"]
    if recommendations:
        for name, count in recommendations.items():
            lines.append(f"{name}\t{count}")
    else:
        lines.append("None")
    return "\n".join(lines)


def roster_warning(summary: dict) -> str | None:
    if not (summary["rated_students_not_in_roster"] or summary["roster_students_not_rated"]):
        return None
    return (
        "Assessment and roster student lists differ. "
        f"Only in assessment: {', '.join(summary['rated_students_not_in_roster']) or 'none'}; "
        f"only in roster: {', '.join(summary['roster_students_not_rated']) or 'none'}."
    )


def save_summary(assessment_file: str | Path, group_roster_file: str | Path,
                 output_file: str | Path) -> dict:
    assessment_file = Path(assessment_file).expanduser()
    group_roster_file = Path(group_roster_file).expanduser()
    output_file = Path(output_file).expanduser()
    for label, path in (("Assessment CSV", assessment_file), ("Project roster CSV", group_roster_file)):
        if not path.is_file():
            raise FileNotFoundError(f"{label} not found: {path}")
    if output_file.resolve() in (assessment_file.resolve(), group_roster_file.resolve()):
        raise ValueError("Report location must differ from the input CSV files")
    summary = summarize_assessment(group_roster_file, assessment_file)
    output_file.write_text(format_summary(summary) + "\n", encoding="utf-8")
    return summary


def process_assessments(assessment_files: list[str | Path], group_roster_file: str | Path | None,
                        output_dir: str | Path) -> tuple[list[tuple[Path, dict]], list[tuple[Path, str]]]:
    output_dir = Path(output_dir).expanduser()
    if not output_dir.is_dir():
        raise NotADirectoryError(f"Output folder not found: {output_dir}")
    assessments = [Path(path).expanduser() for path in assessment_files]
    if not assessments:
        raise ValueError("Select at least one assessment CSV")

    report_names = set()
    for assessment in assessments:
        report_name = f"{assessment.stem}_summary.txt"
        if report_name.casefold() in report_names:
            raise ValueError(f"Two selected assessments would create the same report: {report_name}")
        report_names.add(report_name.casefold())

    completed = []
    errors = []
    for assessment in assessments:
        roster = Path(group_roster_file).expanduser() if group_roster_file else assessment.parent / "Project.csv"
        report = output_dir / f"{assessment.stem}_summary.txt"
        try:
            summary = save_summary(assessment, roster, report)
            completed.append((report, summary))
        except (Exception, SystemExit) as error:
            errors.append((assessment, str(error)))
    return completed, errors


def launch_gui() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("Process Peer Assessment")
    root.resizable(True, False)
    frame = ttk.Frame(root, padding=18)
    frame.grid(sticky="nsew")
    frame.columnconfigure(1, weight=1)
    root.columnconfigure(0, weight=1)

    roster = tk.StringVar()
    output = tk.StringVar()
    output_changed = False
    assessments: list[Path] = []

    def add_assessments() -> None:
        nonlocal output_changed
        filenames = filedialog.askopenfilenames(
            parent=root, title="Select assessment CSV files",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        for filename in filenames:
            path = Path(filename)
            if path not in assessments:
                assessments.append(path)
                assessment_list.insert(tk.END, str(path))
        if filenames and not output_changed:
            output.set(str(assessments[0].parent))

    def remove_assessments() -> None:
        for index in reversed(assessment_list.curselection()):
            del assessments[index]
            assessment_list.delete(index)
        if assessments and not output_changed:
            output.set(str(assessments[0].parent))
        elif not assessments and not output_changed:
            output.set("")

    def choose_roster() -> None:
        filename = filedialog.askopenfilename(
            parent=root, title="Select project roster CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if filename:
            roster.set(filename)

    def choose_output() -> None:
        nonlocal output_changed
        directory = filedialog.askdirectory(
            parent=root, title="Select report folder",
            initialdir=output.get() or str(Path.home()))
        if directory:
            output.set(directory)
            output_changed = True

    ttk.Label(frame, text="Select assessment CSVs. If no roster is selected, each uses Project.csv beside it.").grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
    ttk.Label(frame, text="Assessment CSVs").grid(row=1, column=0, sticky="nw", padx=(0, 10), pady=5)
    assessment_list = tk.Listbox(frame, height=6, width=55, selectmode=tk.EXTENDED)
    assessment_list.grid(row=1, column=1, sticky="ew", pady=5)
    list_buttons = ttk.Frame(frame)
    list_buttons.grid(row=1, column=2, sticky="n", padx=(8, 0), pady=5)
    ttk.Button(list_buttons, text="Add…", command=add_assessments).grid(row=0, column=0, sticky="ew")
    ttk.Button(list_buttons, text="Remove", command=remove_assessments).grid(row=1, column=0, sticky="ew", pady=(6, 0))
    fields = [("Project roster CSV (optional)", roster, choose_roster),
              ("Report folder", output, choose_output)]
    for row, (label, variable, browse) in enumerate(fields, 2):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
        ttk.Entry(frame, textvariable=variable, width=55).grid(row=row, column=1, sticky="ew", pady=5)
        ttk.Button(frame, text="Browse…", command=browse).grid(row=row, column=2, padx=(8, 0), pady=5)

    def run() -> None:
        if not assessments or not output.get().strip():
            messagebox.showerror("Missing selection", "Select assessment CSVs and a report folder.", parent=root)
            return
        try:
            completed, errors = process_assessments(assessments, roster.get().strip() or None, output.get().strip())
        except (Exception, SystemExit) as error:
            messagebox.showerror("Could not process assessments", str(error), parent=root)
            return
        details = [f"Saved {len(completed)} report(s) in:\n{output.get().strip()}"]
        firing_reports = [(path, summary["recommended_for_firing"])
                          for path, summary in completed if summary["recommended_for_firing"]]
        low_response_reports = [(path, summary["respondent_count"])
                                for path, summary in completed if summary["respondent_count"] < 4]
        if firing_reports:
            details.append("Reports with members recommended for firing:\n" + "\n".join(
                f"{path.name}: {', '.join(members)}" for path, members in firing_reports))
        if low_response_reports:
            details.append("Reports with fewer than 4 respondents:\n" + "\n".join(
                f"{path.name}: {count} respondent(s)" for path, count in low_response_reports))
        warnings = [(path, roster_warning(summary)) for path, summary in completed]
        warnings = [(path, warning) for path, warning in warnings if warning]
        if warnings:
            details.append("Student list warnings:\n" + "\n".join(
                f"{path.name}: {warning}" for path, warning in warnings))
        if errors:
            details.append("Could not process:\n" + "\n".join(
                f"{path.name}: {error}" for path, error in errors))
            messagebox.showwarning("Processing finished with errors", "\n\n".join(details), parent=root)
        elif firing_reports or low_response_reports or warnings:
            messagebox.showwarning("Reports saved with warnings", "\n\n".join(details), parent=root)
        else:
            messagebox.showinfo("Reports saved", details[0], parent=root)

    ttk.Button(frame, text="Process assessments", command=run).grid(
        row=4, column=0, columnspan=3, sticky="e", pady=(16, 0))
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        launch_gui()
        sys.exit(0)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assessment_file", help="CSV group peer assessment file")
    parser.add_argument("group_roster_file", nargs="?", default="Project.csv",
                        help="CSV group project roster file (default: Project.csv)")
    args = parser.parse_args()
    try:
        summary = summarize_assessment(args.group_roster_file, args.assessment_file)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    warning = roster_warning(summary)
    if warning:
        print("Warning: " + warning, file=sys.stderr)
    print(format_summary(summary))


