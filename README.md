# Peer Assessment Scripts

These scripts work only with the Canvas peer assessment survey workflow. They create surveys from a Canvas project roster and rubric, then summarize the corresponding Canvas student analysis reports. Other survey systems and generic survey CSV exports are not supported. The scripts can be used through browse windows or from a terminal.

## Requirements

- Python 3.10 or newer with Tkinter for the browse windows.
- For Canvas QTI ZIP export only: install `text2qti` with `python3 -m pip install text2qti`.

On macOS, double-clicking a `.py` file may open it in an editor instead of running it. If that happens, double-click the corresponding `.command` file to open the script's browse window: `Create Surveys.command` or `Process Assessments.command`.

## Input files

- **Project roster CSV:** Download this from the **group page under People** in Canvas. It must be the project/group roster export with `name` and `group_name` columns; the survey creator reads the group name from column 6.
- **Rubric CSV:** A CSV you prepare with one rubric category per row and five rating descriptions. See `rubric.csv` in this folder for an example.
- **Assessment CSVs:** The student analysis report CSVs exported from Canvas after students complete the surveys. Each file should contain one group's responses.

### Rubric CSV structure

Use **six columns per row**, with no header row:

| Column | Content |
| --- | --- |
| 1 | Category name and question text. Start with `Category name:` so the results processor can identify the category. |
| 2 | Description for rating 1. |
| 3 | Description for rating 2. |
| 4 | Description for rating 3. |
| 5 | Description for rating 4. |
| 6 | Description for rating 5. |

The included `rubric.csv` shows the full format. A simplified example is:

```csv
Timeliness: Consider the member's timeliness of work.,Misses deadlines,Often late,Usually on time,Always on time,Finishes early
Participation: Consider the member's contribution.,Does not participate,Rarely participates,Participates sometimes,Participates regularly,Leads and supports others
```

Each row becomes a rubric shown above the five rating choices for every student in the group. If a cell contains a comma, enclose that cell in double quotes as required by CSV formatting.

## Create surveys

1. Double-click `create_survey.py` or run `python3 create_survey.py` in a terminal. If your computer opens `.py` files in an editor on macOS, double-click `Create Surveys.command`.
2. Browse for the project roster CSV. The output folder defaults to the roster's folder.
3. Optionally browse for a rubric CSV. If left blank, the script looks for `rubric.csv` beside the selected project CSV and displays an error if it is missing.
4. Choose an output folder if you want a different location. Optionally select **Create Canvas QTI ZIP files** or **Omit firing recommendation question**.
5. Click **Create surveys**.

The script saves one `<group>_survey.txt` file per group, or one `<group>_survey.zip` file per group when QTI is selected, in the output folder.

Terminal example:

```sh
python3 create_survey.py "path/to/Project.csv" rubric.csv --output-dir surveys
```

Add `--qti` for Canvas QTI ZIP files or `--no-fire` to omit the firing recommendation question. In terminal mode, an omitted rubric path means `rubric.csv` in the **current working directory**, and an omitted `--output-dir` means the current working directory.

## Process assessment results

1. Double-click `process.py` or run `python3 process.py` without arguments to open the browse window. If macOs opens the file in an editor, double-click `Process Assessments.command`.
2. Click **Add…** and select one or several assessment CSVs. You can use **Add…** again for files in another folder, or select files in the list and click **Remove**.
3. Optionally browse for a project roster CSV. If left blank, the script looks for `Project.csv` beside **each** assessment CSV and reports any missing file. A selected roster is used for every assessment.
4. Choose the report folder if needed. It defaults to the folder of the first assessment selected.
5. Click **Process assessments**.

The script saves one `<assessment name without .csv>_summary.txt` report per assessment in the report folder. It also creates `grade.csv` there with one row for **every student in the selected project roster**, including students in groups without a processed assessment and students not assigned to a group. If no roster is selected, it includes students from the `Project.csv` files beside the selected assessments. Its columns are `last name`, `first name`, and `average`, sorted by last name and then first name. The average combines all rubric ratings for that student; a student with no processed ratings receives `0.00`. If a student appears in multiple processed files, their ratings are combined into one average. Running another batch in the same folder replaces `grade.csv` with that batch's grades.

The script processes the remaining files if one assessment fails. After processing, a warning window lists report files with members recommended for firing, report files with fewer than four respondents, and any processing errors or roster mismatches. Two selected files that would produce the same report name must be processed separately or renamed first.

Terminal mode processes one assessment and prints its report to the terminal:

```sh
python3 process.py "path/to/assessment.csv" "path/to/Project.csv"
```

You can redirect the printed report to a file with `> report.txt`. In terminal mode, an omitted roster path means `Project.csv` in the **current working directory**.
