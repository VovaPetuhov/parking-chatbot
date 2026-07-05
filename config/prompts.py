RAG_SYSTEM_PROMPT = """You are a helpful assistant for {parking_name}, a parking facility.

Your role is to:
1. Answer questions about the parking facility using the provided context
2. Be polite, professional, and concise
3. If you don't know the answer based on the context, say so honestly
4. Never make up information not present in the context
5. When discussing reservations, guide users through the process step by step

Context from knowledge base:
{context}

If the context doesn't contain relevant information, politely inform the user that you don't have that specific information and suggest contacting customer service."""

RAG_USER_PROMPT = """User question: {question}

Please provide a helpful and accurate answer based on the context above."""

# Reservation Collection Prompts

RESERVATION_INTENT_PROMPT = """Analyze if the user wants to make a parking reservation.

User message: {user_input}

IMPORTANT: Your answer must be EXACTLY 'yes' or 'no' - nothing else!

Return 'yes' ONLY if the user clearly wants to make a reservation.
Examples of reservation intent:
- "I want to book a parking spot" -> yes
- "Can I reserve a space?" -> yes
- "I'd like to make a reservation" -> yes
- "Book a spot for tomorrow" -> yes
- "What are your opening hours?" -> no
- "How much does it cost?" -> no

Answer (ONLY 'yes' or 'no'):"""

EXTRACT_NAME_PROMPT = """Extract the person's first name from the user's message.

User message: {user_input}

IMPORTANT: Return ONLY the first name, nothing else!
- If a name is found, return just the name
- If no name is found, return EXACTLY 'NOT_FOUND'
- Do NOT add explanations, punctuation, or extra words

Examples:
Input: "My name is John" -> Output: John
Input: "I'm Sarah" -> Output: Sarah
Input: "Call me Mike" -> Output: Mike
Input: "John Smith" -> Output: John
Input: "Yes" -> Output: NOT_FOUND
Input: "I don't know" -> Output: NOT_FOUND

Extracted name:"""

EXTRACT_SURNAME_PROMPT = """Extract the person's last name (surname) from the user's message.

User message: {user_input}

IMPORTANT: Return ONLY the surname, nothing else!
- If a surname is found, return just the surname
- If no surname is found, return EXACTLY 'NOT_FOUND'
- Do NOT add explanations, punctuation, or extra words

Examples:
Input: "My surname is Smith" -> Output: Smith
Input: "Last name is Johnson" -> Output: Johnson
Input: "It's Brown" -> Output: Brown
Input: "Yes" -> Output: NOT_FOUND
Input: "I don't know" -> Output: NOT_FOUND

Extracted surname:"""

EXTRACT_CAR_PLATE_PROMPT = """Extract the car license plate number from the user's message.

User message: {user_input}

IMPORTANT: Return ONLY the plate number, nothing else!
- If a plate is found, return just the plate (keep letters, numbers, spaces, dashes)
- If no plate is found, return EXACTLY 'NOT_FOUND'
- Do NOT add explanations, punctuation, or extra words

Examples:
Input: "My plate is ABC 123" -> Output: ABC 123
Input: "Car number: XY-456-ZZ" -> Output: XY-456-ZZ
Input: "It's BA 123 CD" -> Output: BA 123 CD
Input: "ABC123" -> Output: ABC123
Input: "Yes" -> Output: NOT_FOUND
Input: "I don't know" -> Output: NOT_FOUND

Extracted plate:"""

EXTRACT_DATES_PROMPT = """Extract parking reservation dates from the user's message.

User message: {user_input}
Current date: {current_date}

IMPORTANT: Return dates in EXACTLY this format: YYYY-MM-DD|YYYY-MM-DD
- First date is start date, second is end date
- Use pipe symbol | as separator
- If dates not found or unclear, return EXACTLY 'NOT_FOUND'
- Do NOT add explanations or extra text

Examples:
Input: "From tomorrow to next Friday" (if today is 2024-01-14)
  Output: 2024-01-15|2024-01-19

Input: "January 20th to January 25th" (year 2024)
  Output: 2024-01-20|2024-01-25

Input: "Next Monday for 3 days" (if today is 2024-01-14)
  Output: 2024-01-15|2024-01-18

Input: "I don't know"
  Output: NOT_FOUND

Extracted dates (START|END):"""

CONFIRM_DATA_PROMPT = """You are helping confirm reservation details with the user.

Collected reservation data:
- Name: {name}
- Surname: {surname}
- Car Plate: {car_plate}
- Start Date: {start_date}
- End Date: {end_date}

Please present this information to the user in a friendly way and ask them to confirm if everything is correct.
Mention that they can say 'yes' to confirm or tell you what needs to be changed.

Your response:"""

RESERVATION_COLLECTED_MESSAGE = """Thank you! I have collected all the information for your parking reservation:

Reservation Details:
  1. Name: {name} {surname}
  2. Car Plate: {car_plate}
  3. Start Date: {start_date}
  4. End Date: {end_date}

Your reservation request has been successfully collected!

In the next stage, this request will be sent to our administrator for approval.
You will be notified once your reservation is confirmed.

Is there anything else I can help you with?"""

ASK_NAME_MESSAGE = """Great! I'd be happy to help you with a parking reservation.

Let's start by collecting some information.

What is your first name?"""

ASK_SURNAME_MESSAGE = """Thank you, {name}!

What is your last name (surname)?"""

ASK_CAR_PLATE_MESSAGE = """Perfect, {name} {surname}!

What is your car's license plate number?"""

ASK_DATES_MESSAGE = """Excellent!

When would you like to reserve the parking spot?
Please provide:
  - Start date (when you'll arrive)
  - End date (when you'll leave)

You can say something like "from January 20th to January 25th" or "tomorrow for 3 days"."""

INVALID_INPUT_MESSAGE = """I'm sorry, I couldn't understand that. Could you please try again?

{context}"""

ADMIN_REVIEW_PROMPT = """You are formatting a parking reservation request for administrator review.

Reservation Details:
- ID: {reservation_id}
- Customer: {name} {surname}
- Car Plate: {car_plate}
- Start Date: {start_time}
- End Date: {end_time}
- Requested At: {created_at}

Please format this as a clear, professional summary for the administrator to review.
Include all key details and make it easy to approve or reject.

Your formatted summary:"""

ADMIN_APPROVAL_CONFIRMATION_PROMPT = """Generate a confirmation message for the customer after their reservation was approved.

Customer: {name} {surname}
Car: {car_plate}
Dates: {start_time} to {end_time}
Admin Comment: {admin_comment}

Create a friendly, professional confirmation message that:
1. Congratulates them on approval
2. Confirms the details
3. Provides any next steps

Your confirmation message:"""

ADMIN_REJECTION_MESSAGE_PROMPT = """Generate a rejection message for the customer.

Customer Name: {name}
Rejection Reason: {reason}

Create a polite, empathetic message that:
1. Informs them of the rejection
2. Explains the reason clearly
3. Offers alternatives or next steps if possible

Your rejection message:"""

PENDING_APPROVAL_USER_MESSAGE = """Thank you! Your reservation request has been submitted successfully.

Reservation Details:
- Reservation ID: {reservation_id}
- Name: {name} {surname}
- Car Plate: {car_plate}
- Period: {start_time} to {end_time}

Your request is now pending administrator approval.
You will be notified once a decision is made.

Thank you for your patience!"""