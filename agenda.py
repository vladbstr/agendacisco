from flask import Flask, render_template, request, jsonify, Response, redirect, url_for, session
import json
from werkzeug.security import check_password_hash
from functools import wraps
import urllib
########
##Modificare Vlad
app = Flask(__name__)
app.secret_key = 'admin'  # Secret key for session management

with open('users.json', 'r') as file:
    users = json.load(file)
# Load JSON database
with open('data.json', 'r') as file:
    database = json.load(file)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:  # Check if user is in session
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        
        username = request.form.get('username')
        password = request.form.get('password')

        # Check if user exists and password is correct
        if username in users and check_password_hash(users[username], password):
            session['user'] = username  # Store user in session
            return redirect(url_for('management'))  # Redirect to the management page
        else:
            return render_template('login.html', error="Invalid username or password")

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.pop('user', None)  # Remove user from session
    return redirect(url_for('login'))



def get_section_from_path(database, path_list):
    """Navigates through the JSON structure based on a path list."""
    section = database
    for key in path_list:
        section = section[key]
    return section






@app.route('/management', defaults={'path': None}, methods=['GET'])
@app.route('/management/<path:path>', methods=['GET'])
@login_required
def management(path):
    global database
    path_list = path.split('/') if path else []  # Split path into sections

    # Get the current section based on the path
    try:
        current_section = get_section_from_path(database, path_list)
    except KeyError:
        return "Invalid Path", 404

    # Generate the breadcrumb
    breadcrumb = ' / '.join(path_list) if path_list else 'Home'

    # Sort sub-sections and users
    sub_sections = {key: value for key, value in current_section.items() if isinstance(value, dict) and 'index' in value}
    sub_sections = sort_by_index(sub_sections)

    users = current_section.get('Utilizatori', {})
    users = sort_by_index(users)

    return render_template('management.html', sub_sections=sub_sections, users=users, breadcrumb=breadcrumb, path=path)

@app.route('/add-section', methods=['POST'])
def add_section():
    global database
    data = request.json
    section_name = data.get('section_name')
    path = data.get('path', '')
    path_list = path.split('/') if path else []

    # Get the current section
    current_section = get_section_from_path(database, path_list)

    # Calculate the next available index
    next_index = max([v.get('index', 0) for k, v in current_section.items() if isinstance(v, dict)] + [0]) + 1

    # Add the new section
    current_section[section_name] = {"index": next_index}

    # Save changes to the database
    save_database(database)
    return jsonify({"message": f"Section '{section_name}' added with index {next_index}!"})

@app.route('/add-user', methods=['POST'])
def add_user():
    global database
    data = request.json
    user_name = data.get('user_name')
    user_number = data.get('user_number')
    path = data.get('path', '')
    path_list = path.split('/') if path else []

    # Get the current section
    current_section = get_section_from_path(database, path_list)

    # Ensure 'Utilizatori' key exists
    if 'Utilizatori' not in current_section:
        current_section['Utilizatori'] = {}

    # Calculate the next available index
    next_index = max([v.get('index', 0) for k, v in current_section['Utilizatori'].items()] + [0]) + 1

    # Add the new user
    current_section['Utilizatori'][user_name] = {"numar": user_number, "index": next_index}

    # Save changes to the database
    save_database(database)
    return jsonify({"message": f"User '{user_name}' added with index {next_index}!"})


@app.route('/reorganize', methods=['POST'])
def reorganize():
    global database

    # Sort the database recursively
    database = sort_recursively(database)

    # Save the sorted database to the file
    save_database(database)

    return jsonify({"message": "JSON has been successfully reorganized based on indexes!"})


@app.route('/update', methods=['POST'])
def update():
    global database
    data = request.json  # JSON data from the client

    # Extract new orders
    new_section_order = data.get('sections', [])
    new_user_order = data.get('users', [])

    # Path-based navigation
    path = data.get('path', '')
    if path == "":  # Handle root-level (Home)
        current_section = database
    else:
        path_list = path.split('/')
        try:
            current_section = get_section_from_path(database, path_list)
        except KeyError:
            return jsonify({"error": "Invalid path provided"}), 400

    # Reorder sections
    if new_section_order:
        if not all(name in current_section for name in new_section_order):
            return jsonify({
                "error": "Invalid section names provided",
                "provided_sections": new_section_order,
                "existing_sections": list(current_section.keys())
            }), 400

        reordered_sections = {name: current_section[name] for name in new_section_order}
        current_section.update(reordered_sections)
        for idx, name in enumerate(new_section_order, start=1):
            current_section[name]['index'] = idx

    # Reorder users
    if 'Utilizatori' in current_section and new_user_order:
        if not all(name in current_section['Utilizatori'] for name in new_user_order):
            return jsonify({
                "error": "Invalid user names provided",
                "provided_users": new_user_order,
                "existing_users": list(current_section['Utilizatori'].keys())
            }), 400

        reordered_users = {name: current_section['Utilizatori'][name] for name in new_user_order}
        current_section['Utilizatori'].update(reordered_users)
        for idx, name in enumerate(new_user_order, start=1):
            current_section['Utilizatori'][name]['index'] = idx

    # Save the updated database
    save_database(database)
    return jsonify({"message": "Reordering successful!"})


@app.route('/delete-section', methods=['POST'])
def delete_section():
    global database
    data = request.json
    section_name = data.get('section_name')
    path = data.get('path', '')
    path_list = path.split('/') if path else []

    # Get the current section
    current_section = get_section_from_path(database, path_list)

    # Delete the section
    if section_name in current_section:
        del current_section[section_name]
        # Reindex only the sections
        current_section = reindex_items_sections(current_section)
        save_database(database)
        return jsonify({"message": f"Section '{section_name}' deleted successfully and indexes updated!"})
    else:
        return jsonify({"error": "Section not found"}), 404


    
@app.route('/modify-section', methods=['POST'])
def modify_section():
    global database
    data = request.json
    old_name = data.get('old_name')
    new_name = data.get('new_name')
    path = data.get('path', '')
    path_list = path.split('/') if path else []

    # Get the current section
    current_section = get_section_from_path(database, path_list)

    # Rename the section
    if old_name in current_section:
        current_section[new_name] = current_section.pop(old_name)
        save_database(database)
        return jsonify({"message": f"Section '{old_name}' renamed to '{new_name}' successfully!"})
    else:
        return jsonify({"error": "Section not found"}), 404
    

@app.route('/delete-user', methods=['POST'])
def delete_user():
    global database
    data = request.json
    user_name = data.get('user_name')
    path = data.get('path', '')
    path_list = path.split('/') if path else []

    # Get the current section
    current_section = get_section_from_path(database, path_list)

    # Delete the user
    if 'Utilizatori' in current_section and user_name in current_section['Utilizatori']:
        del current_section['Utilizatori'][user_name]
        # Reindex the remaining users
        current_section['Utilizatori'] = reindex_items(current_section['Utilizatori'])
        save_database(database)
        return jsonify({"message": f"User '{user_name}' deleted successfully and indexes updated!"})
    else:
        return jsonify({"error": "User not found"}), 404


@app.route('/modify-user', methods=['POST'])
def modify_user():
    global database
    data = request.json
    old_name = data.get('old_name')
    new_name = data.get('new_name')
    new_number = data.get('new_number')
    path = data.get('path', '')
    path_list = path.split('/') if path else []

    # Get the current section
    current_section = get_section_from_path(database, path_list)

    # Modify the user
    if 'Utilizatori' in current_section and old_name in current_section['Utilizatori']:
        current_section['Utilizatori'][new_name] = {
            "numar": new_number,
            "index": current_section['Utilizatori'][old_name]['index']
        }
        if new_name != old_name:
            del current_section['Utilizatori'][old_name]
        save_database(database)
        return jsonify({"message": f"User '{old_name}' updated successfully!"})
    else:
        return jsonify({"error": "User not found"}), 404


@app.route('/')
def returnindex():
    return redirect("management")  # sau alt URL complet


def get_ip_from_config():
    with open('config.json', 'r') as file:
        config = json.load(file)
        return config.get("IP", "127.0.0.1")  # Întoarce IP-ul sau un IP default dacă nu este găsit

@app.route('/data', methods=['GET'])
def data():
    """Render the top-level sections as an XML."""
    base_url = f"http://{get_ip_from_config()}:5000"  # Folosește IP-ul din config.json
    xml_output = generate_xml_menu(database, base_url)
    return Response(xml_output, mimetype="text/xml")


@app.route('/cisco-agenda', methods=['GET'])
def cisco_agenda():
    """
    Render sub-sections and users as XML based on the path.
    """
    base_url = f"http://{get_ip_from_config()}:5000"  # Folosește IP-ul din config.json
    path = request.args.get('path', '')  # Get the path parameter
    path_list = path.split("/") if path else []

    # Navigate the JSON structure to get the desired section
    try:
        current_section = get_section_from_path(database, path_list)
    except KeyError:
        return Response("<Error>Invalid Path</Error>", mimetype="text/xml")

    # Generate XML for the current section
    xml_output = generate_xml_menu(current_section, base_url, path)
    return Response(xml_output, mimetype="text/xml")


def generate_xml_menu(data, base_url, path=None):
    """Generate XML from JSON data for the current level, sorted by index."""
    path = path or ""
    xml = ["<CiscoIPPhoneMenu>"]
    xml.append("<Title>AGENDA</Title>")
    xml.append("<Prompt/>")

    # Extract and sort sections by index
    sorted_sections = sorted(
        (item for item in data.items() if isinstance(item[1], dict) and "index" in item[1]),
        key=lambda x: x[1]["index"]
    )



def generate_xml_menu(data, base_url, path=None):
    """Generate XML from JSON data for the current level, sorted by index."""
    path = path or ""
    path_agenda=path.split('/')[-1] if path else 'Agenda'
    xml = ["<CiscoIPPhoneMenu>"]
    xml.append(f"<Title>{path_agenda}</Title>")
    xml.append("<Prompt/>")
    xml_users = ["<CiscoIPPhoneDirectory>"]
    xml_users.append(f"<Title>{path_agenda}</Title>")
    xml_users.append("<Prompt/>")

    # Extract and sort sections by index
    sorted_sections = sorted(
        (item for item in data.items() if isinstance(item[1], dict) and "index" in item[1]),
        key=lambda x: x[1]["index"]
    )

    for section_name, section_data in sorted_sections:
        # Generate URL for each section, only encode the path part
        section_path = f"{path}/{section_name}" if path else section_name
        # Codifica doar path-ul, nu întreaga adresă URL
        encoded_path = urllib.parse.quote(section_path)
        encoded_url = f"{base_url}/cisco-agenda?path={encoded_path}"

        xml.append("<MenuItem>")
        xml.append(f"<Name>{section_name}</Name>")
        xml.append(f"<URL>{encoded_url}</URL>")
        xml.append("</MenuItem>")
        
    if path:  # Dacă suntem într-un submeniu, generează calea părinte
        parent_path = "/".join(path.split("/")[:-1])
        encoded_parent_path = urllib.parse.quote(parent_path)  # Codifică calea
        back_url = f"{base_url}/cisco-agenda?path={encoded_parent_path}"
    else:  # Dacă suntem la nivelul principal, navigăm la pagina de start
        back_url = f"{base_url}/cisco-agenda"
        
    if 'Utilizatori' in data:
        users = data['Utilizatori']
        sorted_users = sorted(users.items(), key=lambda item: item[1]['index'])
        for user_name, user_data in sorted_users:
            xml_users.append("<DirectoryEntry>")
            xml_users.append(f"<Name>{user_name}</Name>")
            xml_users.append(f"<Telephone>{user_data['numar']}</Telephone>")
            xml_users.append("</DirectoryEntry>")
        xml_users.append("<SoftKeyItem>")
        xml_users.append("<Name>Suna</Name>")
        xml_users.append(f"<URL>SoftKey:Dial</URL>")
        xml_users.append("<Position>1</Position>")
        xml_users.append("</SoftKeyItem>")
        xml_users.append("<SoftKeyItem>")
        xml_users.append("<Name>Inapoi</Name>")
        xml_users.append(f"<URL>{back_url}</URL>")
        xml_users.append("<Position>2</Position>")
        xml_users.append("</SoftKeyItem>")
        xml_users.append("<SoftKeyItem>")
        xml_users.append("<Name>Renunta</Name>")
        xml_users.append("<URL>Init:Services</URL>")  # Comandă pentru ieșire directă
        xml_users.append("<Position>3</Position>")
        xml_users.append("</SoftKeyItem>")
        xml_users.append("</CiscoIPPhoneDirectory>")
        return "\n".join(xml_users)
    xml.append("<SoftKeyItem>")
    xml.append("<Name>Inapoi</Name>")
    xml.append(f"<URL>{back_url}</URL>")
    xml.append("<Position>1</Position>")
    xml.append("</SoftKeyItem>")
    xml.append("<SoftKeyItem>")
    xml.append("<Name>Renunta</Name>")
    xml.append("<URL>Init:Services</URL>")  # Comandă pentru ieșire directă
    xml.append("<Position>2</Position>")
    xml.append("</SoftKeyItem>")

    xml.append("</CiscoIPPhoneMenu>")
    return "\n".join(xml)



def reindex_items(items):
    """Reindex the items in a dictionary based on their current order."""
    sorted_items = sorted(items.items(), key=lambda item: item[1].get('index', float('inf')))
    return {name: {**value, "index": idx + 1} for idx, (name, value) in enumerate(sorted_items)}

def reindex_items_sections(items):
    """
    Reindex sections in a dictionary based on their 'index' key.
    Ensures that all remaining sections are indexed sequentially.
    """
    if not isinstance(items, dict):
        return items  # If items is not a dictionary, return it as-is

    # Collect sections that have a valid 'index' key
    indexed_sections = {k: v for k, v in items.items() if isinstance(v, dict) and 'index' in v}

    # Sort sections by their current index
    sorted_sections = sorted(indexed_sections.items(), key=lambda item: item[1]['index'])

    # Reassign sequential indexes starting from 1
    reindexed_sections = {}
    for new_index, (section_name, section_data) in enumerate(sorted_sections, start=1):
        section_data['index'] = new_index  # Update the index in-place
        reindexed_sections[section_name] = section_data

    # Add back non-section items
    non_section_items = {k: v for k, v in items.items() if k not in indexed_sections}
    reindexed_sections.update(non_section_items)

    return reindexed_sections



def sort_by_index(data):
    """Sort a dictionary based on the 'index' key."""
    if isinstance(data, dict):
        return dict(sorted(data.items(), key=lambda item: item[1].get('index', float('inf'))))
    return data

def save_database(database):
    with open('data.json', 'w') as file:
        json.dump(database, file, indent=4)

def sort_recursively(data):
    """Recursively sort sections and users in JSON by their index."""
    if isinstance(data, dict):
        # Separate indexed items from non-indexed items
        indexed_items = {k: v for k, v in data.items() if isinstance(v, dict) and 'index' in v}
        non_indexed_items = {k: v for k, v in data.items() if k not in indexed_items}

        # Sort indexed items by their 'index' key
        sorted_indexed_items = dict(sorted(indexed_items.items(), key=lambda item: item[1]['index']))

        # Recursively sort children
        for key, value in sorted_indexed_items.items():
            sorted_indexed_items[key] = sort_recursively(value)

        # Combine sorted indexed items with non-indexed items
        return {**sorted_indexed_items, **non_indexed_items}
    return data



# Rulare aplicație
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
