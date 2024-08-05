# load_env.py
import os
import importlib.util
from dotenv import load_dotenv
from collections import OrderedDict

def determine_context():
    cwd = os.getcwd()
    directory_name = os.path.basename(cwd)
    parts = directory_name.split('-')
    if len(parts) > 1:
        return parts[1]
    return 'default'

def load_template(template_path):
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f"Template file {template_path} does not exist.")
    
    spec = importlib.util.spec_from_file_location("env_template", template_path)
    env_template = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(env_template)
    return env_template.ENV_VARS

def apply_context_overrides(template_vars, context):    
    context_vars = template_vars.get('base', {}).copy()
    context_vars.update(template_vars.get('sites', {}).get(context, {}))
    context_vars['BASE_DIR'] = os.getcwd()
    context_vars['ENV_CONTEXT'] = context    
    return OrderedDict(sorted(context_vars.items()))

def write_env_file(env_vars, output_path):
    with open(output_path, 'w') as file:
        for key, value in env_vars.items():
            file.write(f'{key}={value}\n')

def load_environment(context='default', template_path='env_template.py', output_path='.env'):
    # Ensure paths are relative to the script's directory
    script_dir = os.path.dirname(__file__)
    template_path = os.path.join(script_dir, template_path)
    output_path = os.path.join(script_dir, output_path)
    
    try:
        template_vars = load_template(template_path)
    except FileNotFoundError as e:
        print(e)
        return
    
    env_vars = apply_context_overrides(template_vars, context)
    write_env_file(env_vars, output_path)
    load_dotenv(output_path)

if __name__ == "__main__":
    context = determine_context()
    load_environment(context)
    print(f"Environment variables for context '{context}' have been written to .env and loaded into the environment")
