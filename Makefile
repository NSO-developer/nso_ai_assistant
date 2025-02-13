# Find correct version here https://developer.chrome.com/docs/chromedriver/downloads
# First digit must be the same between Chromedriver and Chrome
CHROMEDRIVER_VER=113.0.5672.63

chrome:
	sudo apt update
	wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
	sudo dpkg -i google-chrome-stable_current_amd64.deb
	sudo apt-get install -f
	google-chrome --version
	sudo apt-get install chromium-chromedriver

deps:
	pip install -r requirments.txt

build_model_server:
	curl -fsSL https://ollama.com/install.sh | sh
	ollama pull llama3.1:8b
	systemctl start ollama
