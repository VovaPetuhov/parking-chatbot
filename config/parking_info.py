from config.settings import settings

PARKING_INFO = f"""
# {settings.parking_name}

## Location and Contact
Address: {settings.parking_address}
The parking is located in the heart of the city center, easily accessible from main roads.

## Working Hours
Weekdays (Monday-Friday): {settings.working_hours_weekday}
Weekends (Saturday-Sunday): {settings.working_hours_weekend}
Public Holidays: {settings.working_hours_weekend}

The parking operates all year round. Entry gates open at the start time and close at the end time.

## Capacity and Availability
Total parking spaces: {settings.parking_capacity}
The parking includes:
- Standard parking spaces: 120
- Disabled parking spaces: 10
- Electric vehicle charging stations: 15
- Motorcycle parking: 5

Real-time availability can be checked through our system.

## Pricing
Hourly rate: ${settings.price_per_hour} per hour
Daily rate: ${settings.price_per_day} per day (24 hours)
Weekly rate: $250 per week
Monthly rate: $800 per month

Payment methods accepted:
- Credit/Debit cards (Visa, Mastercard, American Express)
- Mobile payments (Apple Pay, Google Pay)
- Cash (at payment machines)

## Facilities and Services
Our parking offers:
- 24/7 video surveillance
- Well-lit areas
- Security personnel on-site
- Car wash service (additional fee)
- Tire pressure check stations
- Clean and maintained restrooms
- Elevators and escalators to all levels

## Reservation System
You can reserve parking spaces in advance through our chatbot system.
Reservation process:
1. Provide your full name
2. Provide your surname
3. Provide your car registration number
4. Specify reservation start date and time
5. Specify reservation end date and time
6. Conferm your reservation

Reservations can be made up to 30 days in advance.
Cancellation is free up to 24 hours before reservation start.

## Rules and Regulations
- Maximum vehicle height: 2.1 meters
- Maximum vehicle length: 5.5 meters
- Speed limit inside parking: 10 km/h
- No smoking in parking areas
- No washing or repairing vehicles (except at designated service area)
- Parking is only allowed in marked spaces
- Kep your parking ticket until exit

## Safety and Security
Your safety is our priority:
- Emergency exits on every level
- Fire extinguishers and safety equipment
- Emergency call buttons
- First aid stations
- Security guards patrolling 24/7
- CCTV monitoring

## Electric Vehicle Charging
We offer 15 charging stations:
- 10 x Level 2 (240V) chargers
- 5 x DC Fast charging stations
Additional fee: $3 per hour for charging

## Accessibility
The parking is fully accessible for persons with disabilities:
- 10 designated disablid parking spaces (closest to elevators)
- Wide spaces for easier access
- Ramps and elevators to all levels
- Accessible restrooms
- Assistance available upon request

## Lost and Found
If you lose items in the parking:
- Contact our staff immediately
- Check with the security office on ground floor
- Items are kept for 30 days
- Call our hotline: +4211-555-0123

## Contact Informatin
Customer Service: +421-555-0123
Email: info@centralBAparketing.com
Emergency: +421-555-0911
Website: www.centralBratislavaParking.com

## Frequently Asked Questions

Q: Can I enter and exit multiple times with the same ticket?
A: No, the ticket is valid for one entry and one exit only. For multiple entries, consider a monthly pass.

Q: What happens if I lose my parking ticket?
A: Contact the security office. You'll need to pay the maximum daily rate and provide vehicle registration proof.

Q: Can I reserve a specific parking spot number?
A: No, we assign spots based on availability. However, you can request preferences (e.g., ground floor, near elevator).

Q: Is the parking suitable for large vehicles/RVs?
A: Standard spaces are for vehicles up to 5.5m length and 2.1m height. For larger vehicles, please contact us in advance.

Q: Do you offer corporate/business accounts?
A: Yes, we offer special rates for businesses. Contact our sales team for details.
"""
