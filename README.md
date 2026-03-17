# Ledger AI - The Bank Statement Reader 🤖🧾

## Overview
Ledger AI is an intelligent system that reads your bank PDF statements and automatically pulls out all the transactions using AI (Language Models). We use a special **Quality Control (QC) workspace** to catch any mistakes the AI makes, and we teach it to write Python code to be mathematically perfect!

This app is built with:
1. **Frontend:** A beautiful website interface (React/Vite).
2. **Backend API:** The core engine that talks to our database (Python FastAPI).
3. **Database:** MariaDB/MySQL to store files and data.

---

## 🛠️ Local Installation & Setup

1. **Database Setup**
   Make sure you have MySQL or XAMPP running. Our database structure is stored in `backend/db/full_schema.sql`. You can dump that file into your database client to create the empty tables.

   ```bash
   cd backend
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

   **Setting up the API Key:**
   You must provide an API key for the AI to work. Create a file named `.env` inside the `backend` folder and add your Gemini API key like this:
   ```env
   GEMINI_API_KEY="your-api-key-here"
   ```

3. **Frontend Setup (React/Node)**
   Open a new terminal, go to the frontend, and download the web building blocks:
   ```bash
   cd frontend
   npm install
   ```

---

## 🚀 How to Run the App Like a Pro!
You don't need to type out all the commands every time. We added a magic script just for you! 

**If you are on Windows:**
Just double-click the **`start.bat`** file in your project folder! 
This will automatically open two black windows (one for the Backend API and one for the Website). **Keep both windows open!** 

*(If you are on Mac/Linux, run `./start.sh` in the terminal instead).*

---

## 🕵️‍♂️ The Ledger AI System: A Guide for Beginners 

The web app is split into **three core functionalities**. Together, they ensure that the AI learns from its mistakes and consistently outputs 100% accurate accounting data.

### 1. Review Documents (The Code Training Ground)
This page is where you teach the AI how to write flawless Python code for new bank formats. 
When a new bank format is uploaded, two methods try to extract the data:
- **The LLM (Baseline):** A smart AI tries to guess where the transactions are. 
- **The Code Parser:** The AI wrote a Python script to do the math. 

We compare the guesses with the script to catch errors. You will see them side-by-side. 
- **Yellow boxes** mean the data (like the date or amount) didn't match perfectly.
- **Red boxes** mean a transaction was entirely missed by one side.

**How you fix it:**
- **Improve Code:** If the Code script missed something, type exactly what is wrong in the "Add QC Remarks" box *(e.g. "You missed the opening balance on page 1")* and click **Improve & Re-run Code**. The AI will rewrite its script!
- **Override LLM:** If the Code is perfect but the LLM hallucinated fake rows, click **Override LLM Baseline**. This tells the system to trust your Code, locking the score at 100%.
- **Save Code:** Once the accuracy hits 100%, click Save to lock in this Python parser forever!

### 2. Random QC Dashboard (The Health Monitor)
Once a Python parser is "Saved" and active, it processes bank statements automatically without human review. However, banks sometimes change their PDF formats, or the code makes a rare mistake!

The **Random QC** page automatically grabs random documents that were processed automatically and audits them. It runs the active code against a fresh LLM baseline again in the background.
- It provides a beautiful dashboard showing **Average Accuracy**, **Highest/Lowest Scores**, and **Pending Reviews**.
- If a document's accuracy drops below the threshold, it gets flagged as **"FLAGGED"**.
- An admin can then click "View Detail" to see a visual ring-chart of the score and the exact matched/unmatched transactions to manually investigate if the code needs to be updated.

### 3. Frequent AI Errors (The Analytics Tracker)
Whenever an admin or user is forced to manually edit a cell that the AI got wrong (like fixing a bad date format, or correcting a hallucinated debit amount), the system tracks it.

The **Frequent AI Errors** page analyses these manual corrections:
- **Field Change Heat Map:** Shows you exactly which data columns (Date, Debit, Credit, Details) are glowing red with the most human corrections.
- **Bank Ranking:** Shows a leaderboard of which banks are causing the most AI failures.
- **Before & After Viewer:** You can expand any document to see precisely what the AI outputted (Before) versus what the human typed (After).
- **Generate LLM Prompt Report:** With one click, the system compiles these recurring errors into an advanced AI prompt to permanently fix underlying system parsing logic across the entire platform!
