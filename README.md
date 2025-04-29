# Power_Outage_Alerts

This project monitors the KPLC Twitter page for preplanned power outages and sends alerts via Telegram. It uses pre-existing cookies for authentication but soon, I'll incorporate an automated cookie generator plus traditional authentication.I will also soon be updating it with better OCR and various ML intergrations.

## Setup

### Prerequisites
- Python 3.x.
- A Telegram bot token from [BotFather](https://core.telegram.org/bots#6-botfather), plus the relevant chat_id.

### Installation Steps

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Moses-Muchiri/Power_Outage_Alerts.git
   cd Power_Outage_Alerts
   ```
2. **Install all the necessary dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the application**:
   ```bash
   python app.py
   ```