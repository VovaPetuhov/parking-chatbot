import logging
import sys

from config.logging_config import setup_logging
from config.settings import settings
from graphs.chatbot_graph import ParkingChatbot, get_chatbot

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_welcome():
    print("=" * 70)
    print(f"{settings.parking_name} - Chatbot Assistant")
    print("=" * 70)
    print()
    print("Welcome! I can help you with:")
    print("  - General parking information")
    print("  - Working hours and pricing")
    print("  - Parking availability")
    print("  - Reservation process")
    print()
    print("Type 'quit' or 'exit' to end the conversation")
    print("Type 'help' for more information")
    print("Type 'reset' to start a new conversation")
    print("-" * 70)
    print()


def print_help():
    print()
    print("=" * 70)
    print("  Available Commands")
    print("=" * 70)
    print()
    print("  quit/exit     - Exit the chatbot")
    print("  help          - Show this help message")
    print("  reset         - Start a new conversation")
    print("  stats         - Show chatbot statistics")
    print()
    print("  Just type your question to chat!")
    print()


def print_stats(chatbot: ParkingChatbot):
    print()
    print("=" * 70)
    print("  Chatbot Statistics")
    print("=" * 70)
    print()
    try:
        stats = chatbot.rag_system.get_stats()
        print(f"Model: {stats.get('llm_model', 'N/A')}")
        print(f"Parking: {stats.get('parking_name', 'N/A')}")
        print(f"Documents in KB: {stats.get('vectorstore', {}).get('total_documents', 'N/A')}")
        print(f"Embedding Model: {stats.get('vectorstore', {}).get('embedding_model', 'N/A')}")
    except Exception as e:
        print(f"Error getting stats: {e}")
    print()


def interactive_mode():
    
    print_welcome()
    
    try:
        settings.validate_config()
        print("Initialising chatbot...")
        chatbot: ParkingChatbot = get_chatbot()
        print("Chatbot ready!")
        print()
        
        conversation_id = "cli_session"
        
        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.lower() in ['quit', 'exit']:
                    print()
                    print("Thank you for using our chatbot! Have a great day!")
                    print()
                    break
                
                elif user_input.lower() == 'help':
                    print_help()
                    continue
                
                elif user_input.lower() == 'reset':
                    import uuid
                    conversation_id = f"cli_session_{uuid.uuid4().hex[:8]}"
                    print()
                    print("Conversation reset. Starting fresh!")
                    print()
                    continue
                
                elif user_input.lower() == 'stats':
                    print_stats(chatbot)
                    continue
                
                response = chatbot.chat(user_input, conversation_id=conversation_id)
                
                print()
                print(f"Bot: {response}")
                print()
                
            except KeyboardInterrupt:
                print()
                print("Interrupted. Type 'quit' to exit or continue chatting.")
                print()
                continue
            
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                print(f"Sorry, an eror occurred: {e}")
                print("Please try again or type 'quit' to exit.")
    
    except KeyboardInterrupt:
        print()
        print()
        print("Goodbye!")
        print()
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print()
        print(f"Fatl error: {e}")
        print("Please check your configuration and try again.")
        print()
        sys.exit(1)


def main():
    args = sys.argv[1:]

    # Check for quiet mode flag
    quiet = "--quiet" in args or "-q" in args
    verbose = "--verbose" in args or "-v" in args
    if quiet:
        setup_logging(quiet=True)
    elif verbose:
        setup_logging(level="DEBUG")
    else:
        setup_logging()

    if "--help" in args or "-h" in args:
        print()
        print("Parking Chatbot - Usage")
        print()
        print("python main.py              Run in interactive mode (default)")
        print("python main.py --help       Show this help")
        print()
        print("Before running, make sure to:")
        print("1. Create .env file (copy from .env.example)")
        print("2. Run: python init_db.py (to initialize database)")
        print()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
