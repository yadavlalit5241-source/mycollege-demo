import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).parent
PORT = int(os.environ.get("PORT", "3000"))


def load_dotenv():
	for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines() if (ROOT / ".env").exists() else []:
		line = line.strip()
		if line and not line.startswith("#") and "=" in line:
			key, value = line.split("=", 1)
			os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class Handler(BaseHTTPRequestHandler):
	def send_json(self, status, body):
		payload = json.dumps(body).encode("utf-8")
		self.send_response(status)
		self.send_header("Content-Type", "application/json; charset=utf-8")
		self.send_header("Content-Length", str(len(payload)))
		self.end_headers()
		self.wfile.write(payload)

	def do_POST(self):
		if self.path != "/api/chat":
			return self.send_json(404, {"error": "Not found."})
		if not os.environ.get("GROQ_API_KEY"):
			return self.send_json(500, {"error": "GROQ_API_KEY is not configured on the server."})
		try:
			length = int(self.headers.get("Content-Length", "0"))
			body = json.loads(self.rfile.read(length))
			message = body.get("message", "").strip()
			if not message:
				return self.send_json(400, {"error": "Enter a message first."})
			request_body = json.dumps({
				"model": os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
				"temperature": 0.4,
				"max_tokens": 700,
				"messages": [
					{"role": "system", "content": "You are Classroom Copilot, a concise, supportive assistant for teachers. Give practical, trauma-informed classroom-management advice. Protect student privacy and never invent student information. Use plain text with short paragraphs or numbered steps."},
					{"role": "user", "content": message},
				],
			}).encode("utf-8")
			request = Request("https://api.groq.com/openai/v1/chat/completions", data=request_body, headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}", "Content-Type": "application/json"})
			with urlopen(request, timeout=45) as result:
				data = json.loads(result.read().decode("utf-8"))
			return self.send_json(200, {"reply": data.get("choices", [{}])[0].get("message", {}).get("content", "Please try again.")})
		except HTTPError as error:
			try:
				data = json.loads(error.read().decode("utf-8"))
			except (json.JSONDecodeError, UnicodeDecodeError):
				data = {}
			return self.send_json(error.code, {"error": data.get("error", {}).get("message", "Groq returned an error.")})
		except (URLError, TimeoutError) as error:
			return self.send_json(502, {"error": f"Could not reach Groq: {error.reason if isinstance(error, URLError) else error}"})
		except (json.JSONDecodeError, ValueError) as error:
			return self.send_json(400, {"error": str(error)})
		except Exception as error:
			return self.send_json(500, {"error": str(error)})

	def do_GET(self):
		requested = "/index.css/index.html" if self.path == "/" else self.path.split("?", 1)[0]
		file_path = (ROOT / requested.lstrip("/")).resolve()
		if ROOT.resolve() not in file_path.parents or not file_path.is_file():
			return self.send_json(404, {"error": "Not found."})
		content_types = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8"}
		payload = file_path.read_bytes()
		self.send_response(200)
		self.send_header("Content-Type", content_types.get(file_path.suffix, "application/octet-stream"))
		self.send_header("Content-Length", str(len(payload)))
		self.end_headers()
		self.wfile.write(payload)


if __name__ == "__main__":
	load_dotenv()
	print(f"Classroom Copilot running at http://localhost:{PORT}")
	ThreadingHTTPServer(("localhost", PORT), Handler).serve_forever()