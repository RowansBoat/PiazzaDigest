from piazza_api import Piazza
from transformers import pipeline
import time
from piazza_api.exceptions import RequestError
import json

# Load credentials from config.json
with open("config.json") as f:
    config = json.load(f)

email = config["PIAZZA_EMAIL"]
password = config["PIAZZA_PASSWORD"]

# Authenticate with Piazza
p = Piazza()
p.user_login(email, password)

# Connect to a class
network = p.network("PIAZZA_CLASSCODE")

# Fetch the 10 most recent posts with retry logic
recent_posts = []
count = 0

for post_id in network.get_feed()["feed"][:10]:  # Get only the 10 most recent post IDs
    retry_delay = 2  # Start with a 2-second delay

    while True:
        try:
            print(f"📥 Fetching post {post_id['id']}...")
            post = network.get_post(post_id["id"])  # Get full post content
            time.sleep(2)  # Prevent rate-limiting
            print(f"✅ Processed post {post_id['id']}")

            recent_posts.append(post["history"][0]["content"])  # Extract post content
            count += 1
            break  # Exit retry loop if successful
        except RequestError:
            print(f"⚠️ Rate limit hit! Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay *= 2  # Increase wait time (exponential backoff)
            if retry_delay > 16:  # Prevent excessive waiting
                print(f"❌ Skipping post {post_id['id']} after multiple failed attempts.")
                break

# Load the summarization model
print("\n🔄 Loading summarization model...")
summarizer = pipeline("summarization", model="facebook/bart-large-cnn", device=-1)
print("✅ Model loaded!\n")

def extract_relevant_info(post):
    """Extracts the question and useful answers from a Piazza post."""
    # Extract the question (original post)
    question = post["history"][0]["content"] if "history" in post else ""

    # Extract endorsed answers (from instructors or "good" responses)
    answers = []
    if "children" in post:
        for child in post["children"]:
            if child["type"] == "i" or child.get("tag_good") or child.get("tag_endorse"):
                answers.append(child["history"][0]["content"])

    return f"Question: {question}\nAnswers: {' '.join(answers)}\n\n"


def summarize_all_posts(posts):
    """Summarizes all Piazza posts together into one meaningful summary."""
    print("\n🔄 Collecting all post information...")

    # Extract and combine all questions & answers
    all_text = "\n".join(extract_relevant_info(post) for post in posts)

    # Ensure we don't exceed the model's input length
    max_input_length = 4096  # Larger models support more input tokens
    if len(all_text) > max_input_length:
        print("⚠️ Text too long, truncating...")
        all_text = all_text[:max_input_length]

    print("\n🔄 Generating overall summary...")
    try:
        summary = summarizer(all_text, max_length=300, min_length=100, do_sample=False)
        return f"\n📜 **Overall Summary:**\n{summary[0]['summary_text']}"
    except Exception as e:
        return f"❌ Error generating summary: {e}"


# Run summarization on all recent posts
print("\n--- Summarizing Piazza Discussions ---\n")
overall_summary = summarize_all_posts(recent_posts)
print(overall_summary)

