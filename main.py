from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

app = FastAPI()

# Define a Pydantic model for request body validation (optional but recommended)
class Item(BaseModel):
  question:str
  chrt_type:str

'''def llm_chart(question,chrt_type):
    print("hi")
    return "hi"
'''

from Langresp import llm_chart as actual_llm_chart

def llm_chart(question, chrt_type):
    return actual_llm_chart(question, chrt_type)




@app.post("/process_item")
async def process_item_api(item: Item):  # Use the Pydantic model for input validation
    """
    POST API endpoint to process an item.
    """
    try:
        result = llm_chart(item.question, item.chrt_type)
        return result  # FastAPI will automatically convert the dictionary to JSON

    except HTTPException as e:  # Catch HTTPExceptions and re-raise them to let FastAPI handle the response.
        raise  # Re-raise the exception so FastAPI can create the proper error response.
    except Exception as e: # Catch any other exceptions and convert them to HTTPExceptions
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {e}")



# Example of how to run the FastAPI app using Uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)  # Change host/port as needed.