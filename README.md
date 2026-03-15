# Ledger AI - The Bank Statement Reader 🤖🧾

## Overview
Ledger AI is an intelligent system that reads your bank PDF statements and automatically pulls out all the transactions using AI (Language Models). We use a special **Quality Control (QC) Panel** to catch any mistakes the AI makes, and we teach it to write Python code to be mathematically perfect!

This app is built with:
1. **Frontend:** A beautiful website interface (React/Vite).
2. **Backend API:** The core engine that talks to our database (Python FastAPI).
3. **Database:** MariaDB/MySQL to store files and data.

---

## 🛠️ Local Installation & Setup

1. **Database Setup**
   Make sure you have MySQL or XAMPP running. Our database structure is stored in `backend/db/full_schema.sql`. You can dump that file into your database client.

2. **Backend Setup (Python)**
   Open a terminal, go into the backend folder, and install the rules:
   ```bash
   cd backend
   .\venv\Scripts\activate
   pip install -r requirements.txt
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

*(If you ever stop the app, just close those black terminal windows).*

---

## 🕵️‍♂️ The QC Panel: A Guide for Beginners 

The **Quality Control (QC) Panel** is where you act as the teacher for the AI. You make sure the AI extracted the row data correctly. 

### What are we comparing?
When a PDF is uploaded, two things try to read it:
1. **The LLM (Baseline):** A smart AI tries to guess where the transactions are. Sometimes it hallucinates or guesses wrong!
2. **The Code Parser:** The AI wrote a Python script to do the math. 

We compare the guesses with the script to catch errors. To become permanent, the script MUST score **99% or 100% Accuracy**.

### Step-by-Step: How to Use the QC Panel

Here is exactly what you do when you open the QC Panel:

👉 **Step 1: Upload a PDF**
Click the **Upload** button and select your bank statement PDF. Tell the app what bank it is. Wait for the AI to process it.

👉 **Step 2: Go to the "Review Documents" Page**
Look at the list of pending documents. Click on **"Review"** for any document that has a low score or a yellow/red warning.

👉 **Step 3: Spot the Mistakes (Red & Yellow boxes)**
On the left side of the screen, you will see what the Code found. On the right side, you will see what the LLM found.
- If a row is missing on one side, it will be highlighted in **Red**.
- If the date, amount, or description doesn't perfectly match, it will be highlighted in **Yellow**.

👉 **Step 4: Fix It! (Two Options)**

**Option A: Add Remarks to Improve the Code (If the Code is Wrong!)**
If the Code missed a transaction, type exactly what is wrong in the "Add QC Remarks" box. 
*(Example: "You missed the opening balance transaction on page 1")*
Then click **"Improve & Re-run Code"**. The AI will learn from your comment, rewrite its Python script, and try again!

**Option B: Override the LLM (If the Code is Perfect but LLM is stupid!)**
Sometimes the LLM hallucinates fake transactions, but the left side Code got it perfectly right. 
Click the **"Override LLM Baseline"** button. This tells the computer: *"Trust the Code, delete the stupid LLM guess, and lock the score at 100%."*

👉 **Step 5: Save & Finish!**
Once the accuracy hits 100%, the big **"Save Code"** button will turn green. Click it! The document is now marked as **REVIEWED** and the AI has learned the format forever!
