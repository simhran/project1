#this is new folder
#project files hello world
#project files hello world
# ///script
# requires-python=">=3.13"
# dependencies=[
#     "fastapi",
#     "uvicorn",
#     "requests"
# ]
# ///
from fastapi import FastAPI, HTTPException,status
from fastapi.middleware.cors import CORSMiddleware
import requests
from subprocess import run
import requests
import logging
import os
import json
app=FastAPI()

response_format={
    "type":"json_schema",
    "json_schema":{
        "name":"task_runner",
        "schema":{
            "type":"object",
            "required":["python_dependencies","python_code"],
            "properties":{
                "python_code":{
                    "type":"string",
                    "description":"Python code to perform task."
                },
                "python_dependencies":{
                    "type":"array",
                    "items":{
                        "type":"object",
                        "properties":{
                            "module":{
                                "type":"string",
                                "description":"Name of python module"
                            }
                        },
                        "required":["module"],
                        "additionalProperties":False
                    }
                }
            }
        }
    }
}
primary_prompt="""
You are an automated agent, so generate python code that does the specified task.
Assume uv and python are preinstalled.
If you need to run any uv script, then use 'uv run {nameofscript} arguments'
Assume that the code you generate will be executed inside a docker container.
Inorder to perform any task if some python package is required to be installed, provide name of those modules.
"""

def resend_request(task,code,error):
    url="https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
    update_task="""
Update the python code
{code}
---
For below task
{task}
---
Error encountered while running task
{error}
"""
    data={
        "model":"gpt-4o-mini",
        "messages":[
            {
                "role":"user",
                "content":update_task
            },
            {
                "role":"system",
                "content":f"""{primary_prompt}"""
            }
        ],
        "response_format":response_format
    }

def llm_code_executer(python_dependencies,python_code):
    dependencies_str = ''.join(f'# "{dependency["module"]}",\n' for dependency in python_dependencies)
    inline_metadata_script=f"""
# ///script
# requires-python=">=3.13"
# dependencies=[{dependencies_str}# ]
#///
"""
    with open("llm_code.py","w") as f:
        f.write(inline_metadata_script)
        f.write(python_code)
    
    try:
        output=run(["uv","run","llm_code.py"], capture_output=True, text=True, cwd=os.getcwd())
        std_err=output.stderr.split('\n')

        std_out= output.stdout
        exit_code= output.returncode

        for i in range(len(std_err)):
            if std_err[i].lstrip().startswith('File'):
                raise Exception(std_err[i:])
            return "success"
    except Exception as e:
        logging.info(e)
        return {"error":error}
app.add_middleware (
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['GET', 'POST'],
    allow_headers=['*']
)
AIPROXY_Token=os.getenv("AIPROXY_TOKEN")
headers={
    "Content-Type": "application/json",
    "Authorization":f"Bearer {AIPROXY_Token}"
}

@app.get("/")
def home():
    return {"Running"}

def task_runner(task:str):
    url="https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
    data={
        "model":"gpt-4o-mini",
        "messages":[
            {
                "role":"user",
                "content":task
            },
            {
                "role":"system",
                "content":f"""{primary_prompt}"""
            }
        ],
        "response_format":response_format
    }
    print("Sending request to:", url)
    print("Headers:", headers)
    print("Payload:", json.dumps(data, indent=2))
    response=requests.post(url=url, headers=headers, json=data)
    r=response.json()
    python_dependencies=json.loads(r['choices'][0]['message']['content'])['python_dependencies']
    python_code=json.loads(r['choices'][0]['message']['content'])['python_code']
    output=llm_code_executer(python_dependencies,python_code)

    limit=0
    while limit<2:
        if output == "success":
            return "task completed successfully"
        elif output['error']:
            with open('llm_code.py','r') as f:
                code=f.read()
            response=resend_request(task,code,output['error'])
            r=response.json()
            python_dependencies=json.loads(r['choices'][0]['message']['content'])['python_dependencies']
            python_code=json.loads(r['choices'][0]['message']['content'])['python_code']
            output=llm_code_executer(python_dependencies,python_code)
        limit+=1

    return r

if __name__=='__main__':
    import uvicorn
    uvicorn.run (app, host="0.0.0.0", port=8000)
