from flask import Flask, request, jsonify, Response, stream_with_context, render_template
import requests
import json
from datetime import datetime
import uuid

app = Flask(__name__)

# Store conversations in memory (in production, use a database)
conversations = {}

class Conversation:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.messages = []
        self.created_at = datetime.now()
    
    def add_message(self, role, content):
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now()
        })
    
    def get_context(self):
        # Convert messages to Ollama format
        return [{"role": msg["role"], "content": msg["content"]} 
                for msg in self.messages]

def stream_ollama_response(prompt, conversation_id):
    # Ollama API endpoint
    url = "http://localhost:11434/api/chat"
    
    # Get or create conversation
    if conversation_id not in conversations:
        conversations[conversation_id] = Conversation()
    
    conversation = conversations[conversation_id]
    
    # Add user message to conversation
    conversation.add_message("user", prompt)
    
    # Prepare the request payload
    payload = {
        "model": "llama3.2:1b-instruct-q4_K_M",  # Change this to your model
        "messages": conversation.get_context(),
        "stream": True
    }

    # Make request to Ollama
    response = requests.post(url, json=payload, stream=True)
    
    assistant_response = ""
    
    for line in response.iter_lines():
        if line:
            json_response = json.loads(line)
            if 'message' in json_response:
                chunk = json_response['message'].get('content', '')
                assistant_response += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
    
    # After streaming is complete, add assistant's message to conversation
    conversation.add_message("assistant", assistant_response)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    prompt = data.get('prompt')
    conversation_id = data.get('conversation_id')
    
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400
    
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
    
    return Response(
        stream_with_context(stream_ollama_response(prompt, conversation_id)),
        content_type='text/event-stream'
    )

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    return jsonify({
        conv_id: {
            "messages": conv.messages,
            "created_at": conv.created_at.isoformat()
        } for conv_id, conv in conversations.items()
    })

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)