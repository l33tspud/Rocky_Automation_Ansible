# generate_patch_report.py
import json
import csv
import re
from datetime import datetime

# --- Configuration ---
JSON_INPUT_FILE = 'validation_raw_results.json'
CSV_OUTPUT_FILE = 'monthly_patching_report.csv'
MARKDOWN_OUTPUT_FILE = 'monthly_patching_report.md'
CHECKLIST_DATE = datetime.now().strftime("%Y-%m-%d") # Today's date for the checklist

# --- Functions to extract data from Ansible debug messages ---

def extract_value(output_lines, prefix):
    """Extracts a value from a list of strings based on a prefix."""
    for line in output_lines:
        if line.startswith(prefix):
            return line.split(':', 1)[1].strip()
    return "N/A"

def parse_ansible_json(json_data):
    results = {}
    # Iterate through each host's tasks
    for host, host_data in json_data.get('plays', [])[0].get('tasks', {})[-1].get('hosts', {}).items():
        # The relevant information is in the 'debug' task output, specifically 'msg'
        # We need to find the specific debug tasks by looking for their names/patterns
        # and extract the messages.

        # The last debug task usually aggregates everything
        # We need to find the specific debug tasks by name as they are executed sequentially
        # and stored in the results.

        # Look for the relevant tasks by name, which store their output in the 'results' array
        # of the host_data. We need to parse all debug messages.

        all_debug_msgs = []
        for task_output in host_data.get('tasks', []):
            if task_output.get('task', {}).get('name') == 'Display Last System Reboot Date and Time':
                all_debug_msgs.append(task_output.get('result', {}).get('msg'))
            if task_output.get('task', {}).get('name') == 'Display Date of Last Package Upgrade':
                all_debug_msgs.append(task_output.get('result', {}).get('msg'))
            if task_output.get('task', {}).get('name') == 'Display Current Active Kernel Version and Build Date':
                all_debug_msgs.append(task_output.get('result', {}).get('msg'))
            if task_output.get('task', {}).get('name') == 'Display Date of Last ClamAV Freshclam Update':
                # This one has multiline output
                msg = task_output.get('result', {}).get('msg', '').strip()
                all_debug_msgs.extend(msg.splitlines())
            if task_output.get('task', {}).get('name') == 'Display Java Running Status':
                # This one has multiline output
                msg = task_output.get('result', {}).get('msg', '').strip()
                all_debug_msgs.extend(msg.splitlines())


        last_reboot = extract_value(all_debug_msgs, "Last System Reboot Date/Time:")
        last_pkg_upgrade = extract_value(all_debug_msgs, "Date of Last Package Upgrade:")
        kernel_version = extract_value(all_debug_msgs, "Current Active Kernel Version and Build Date:")
        clamav_update = extract_value(all_debug_msgs, "ClamAV Freshclam Last Database Update:")
        java_status = extract_value(all_debug_msgs, "Java Running Status:")


        # Simplified Status based on availability and basic checks
        rocky_updated_status = "N/A"
        if last_pkg_upgrade != "N/A - Could not determine from DNF history.":
            rocky_updated_status = f"Last Pkg: {last_pkg_upgrade.split(' ')[0]}" # Just the date
            # You might want to add logic here to compare `last_pkg_upgrade` with your expected patch date
            # For example: if (datetime.strptime(last_pkg_upgrade.split(' ')[0], '%Y-%m-%d') >= expected_patch_date): "YES" else "NO"

        clamav_updated_status = "N/A"
        if "database file not found" not in clamav_update:
            clamav_updated_status = f"Last AV: {clamav_update.split(' ')[0]}" # Just the date
            # Similarly, compare clamav_update with an expected date

        # Assuming Java is 'Yes, Java processes found.' or 'No, Java processes not found.'
        java_running_status = "Yes" if "Yes, Java processes found." in java_status else "No"


        results[host] = {
            'Rocky Updated': rocky_updated_status,
            'ClamAV Updated': clamav_updated_status,
            'Last Reboot': last_reboot,
            'Kernel Version': kernel_version,
            'Java Running': java_running_status,
            # Add other data if needed from your ansible output
        }
    return results

# --- Main execution ---
if __name__ == "__main__":
    try:
        with open(JSON_INPUT_FILE, 'r') as f:
            ansible_json_output = json.load(f)

        parsed_results = parse_ansible_json(ansible_json_output)

        # Generate CSV Report
        with open(CSV_OUTPUT_FILE, 'w', newline='') as csvfile:
            fieldnames = ['Host', 'Rocky Updated', 'ClamAV Updated', 'Last Reboot', 'Kernel Version', 'Java Running']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for host, data in parsed_results.items():
                row = {'Host': host}
                row.update(data)
                writer.writerow(row)
        print(f"CSV report generated: {CSV_OUTPUT_FILE}")

        # Generate Markdown Report (useful for Gist, Wiki, README)
        with open(MARKDOWN_OUTPUT_FILE, 'w') as mdfile:
            mdfile.write(f"# Monthly Patching Report - {CHECKLIST_DATE}\n\n")
            mdfile.write("| Host | Rocky Updated | ClamAV Updated | Last Reboot | Kernel Version | Java Running |\n")
            mdfile.write("|---|---|---|---|---|---|\n")
            for host, data in parsed_results.items():
                mdfile.write(f"| {host} | {data['Rocky Updated']} | {data['ClamAV Updated']} | {data['Last Reboot']} | {data['Kernel Version']} | {data['Java Running']} |\n")
            mdfile.write("\n")
            mdfile.write("---")
            mdfile.write("\n\n*Note: This report covers Rocky Linux servers and ClamAV status only. Other systems (Firewalls, vSphere, etc.) require separate validation methods.*")
        print(f"Markdown report generated: {MARKDOWN_OUTPUT_FILE}")


    except FileNotFoundError:
        print(f"Error: {JSON_INPUT_FILE} not found. Please run the Ansible playbook with JSON output first.")
    except Exception as e:
        print(f"An error occurred: {e}")
