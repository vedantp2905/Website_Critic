import base64
import os
import shutil
import time
from docx import Document
from io import BytesIO
from openai import OpenAI
import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from PIL import Image
import io


def capture_full_page_screenshots(url, output_folder):
    # Delete the output folder if it already exists
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    
    # Create the output folder
    os.makedirs(output_folder)

    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--headless")
    
    # Set up the webdriver (Chromium in this example)
    driver = webdriver.Chrome(
            service=Service(
                ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
            ),
            options=options,
        )
    
    try:
        # Open the URL
        driver.get(url)
        
        # Wait for the page to load
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # Get the page dimensions
        total_height = driver.execute_script("return document.body.scrollHeight")
        viewport_height = driver.execute_script("return window.innerHeight")
        
        # Calculate the number of screenshots needed
        num_screenshots = total_height // viewport_height + 1
        
        screenshot_paths = []
        
        for i in range(num_screenshots):
            # Calculate scroll position
            scroll_height = i * viewport_height
            if i > 0:
                scroll_height -= 100  # Overlap by 100 pixels
            
            # Scroll to position
            driver.execute_script(f"window.scrollTo(0, {scroll_height});")
            
            # Wait for any dynamic content to load
            time.sleep(1)
            
            # Capture the screenshot
            screenshot = driver.get_screenshot_as_base64()
            img_data = base64.b64decode(screenshot)
            img = Image.open(io.BytesIO(img_data))
            
            # Save the screenshot
            filename = f"screenshot_{i+1:03d}.png"
            file_path = os.path.join(output_folder, filename)
            img.save(file_path)
            screenshot_paths.append(file_path)
            
            print(f"Captured and saved screenshot {i+1} of {num_screenshots}")
        
        print(f"All screenshots saved in folder: {output_folder}")
        
        return screenshot_paths
        
    finally:
        # Close the browser
        driver.quit()


def analyze_all_screenshots(api_key, screenshot_paths):
    client = OpenAI(api_key=api_key)
    
    base64_images = []
    for i, path in enumerate(screenshot_paths, start=1):
        with open(path, "rb") as image_file:
            base64_images.append({
                "index": i,
                "data": base64.b64encode(image_file.read()).decode('utf-8')
            })
    
    messages = [
        {
            "role": "system",
            "content": """You are an expert in website user interface (UI) and user experience (UX) design, as well as content analysis. Your task is to analyze screenshots of websites and provide detailed, structured reports on their UI/UX and content quality. Your analysis should be thorough and based on the following criteria:

            1. **UI/UX Evaluation**:
                - Navigation Structure and Usability
                - Layout and Visual Hierarchy
                - Accessibility Features
                - Visual Design and Appeal
                - Interaction Design
                - Call-to-Action Effectiveness
                - Consistency

            2. **Content Quality Assessment**:
                - Content Clarity and Readability
                - Relevance to Target Audience
                - Engagement Factors (tone, style, multimedia use)
                - Call-to-Action Effectiveness
                - Branding and Messaging Consistency
                - Content Organization and Structure

            For each point you make, clearly reference the specific screenshot number you're referring to. Your final report should include a summary of key findings, prioritization of issues based on impact and effort required to fix them, and suggested key performance indicators (KPIs) to track improvements."""
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": """Analyze these screenshots of a website for UI/UX and content. For each point you make, reference the specific screenshot number you're referring to.

                1. Evaluate the user interface and user experience of the website:
                   - Navigation Structure and Usability
                   - Layout and Visual Hierarchy
                   - Accessibility Features
                   - Visual Design and Appeal
                   - Interaction Design
                   - Call-to-Action Effectiveness
                   - Consistency

                2. Assess the content quality and effectiveness of the website:
                   - Content Clarity and Readability
                   - Relevance to Target Audience
                   - Engagement Factors (tone, style, multimedia use)
                   - Branding and Messaging Consistency
                   - Content Organization and Structure

                3. Provide a comprehensive report that:
                   - Summarizes key findings from each analysis (UI/UX and Content)
                   - For each issue identified:
                     a. Clearly state the problem and reference the relevant screenshot(s)
                     b. Explain its impact on the website's performance
                     c. Provide a specific, actionable solution
                     d. Estimate the effort required (Low/Medium/High)
                     e. Predict the potential impact of implementing the solution (Low/Medium/High)
                   - Prioritize the solutions based on their potential impact and required effort
                   - Propose an implementation timeline
                   - Suggest key performance indicators to track improvement

                Remember to reference specific screenshot numbers for each point you make in your analysis.
                The report should be very detailed."""},
            ] + [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img['data']}"}} for img in base64_images]
        }
    ]
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=4000,
    )
    
    return response.choices[0].message.content

# Streamlit web application
def main():
    st.header('AI Website UX and Content Critic')
    
    # Initialize session state
    if 'generated_content' not in st.session_state:
        st.session_state.generated_content = None
    if 'screenshots' not in st.session_state:
        st.session_state.screenshots = None

    with st.sidebar:
        with st.form('OpenAI'):
            api_key = st.text_input('Enter your OpenAI API key', type="password")
            submitted = st.form_submit_button("Submit")

    if api_key:
        url = st.text_input("Enter your URL")
        
        if st.button("Critique It!"):
            with st.spinner("Capturing screenshots..."):
                output_folder = "webpage_screenshots"
                screenshot_paths = capture_full_page_screenshots(url, output_folder)
                st.session_state.screenshots = screenshot_paths
            
            with st.spinner("Critiquing..."):
                st.session_state.generated_content = analyze_all_screenshots(api_key, screenshot_paths)

        # Display screenshots
        if st.session_state.screenshots:
            st.subheader("Screenshots")
            cols = st.columns(3)
            for i, screenshot_path in enumerate(st.session_state.screenshots):
                with cols[i % 3]:
                    st.image(screenshot_path, caption=f"Screenshot {i+1}", use_column_width=True)

        # Display content if it exists in session state
        if st.session_state.generated_content:
            st.subheader("AI Critique")
            st.markdown(st.session_state.generated_content)

            doc = Document()

            # Add URL to the document
            doc.add_heading(url, 0)

            # Add AI-generated content to the document
            doc.add_paragraph(st.session_state.generated_content)

            # Add screenshots to the document
            doc.add_heading("Screenshots", level=1)
            for i, screenshot_path in enumerate(st.session_state.screenshots):
                doc.add_picture(screenshot_path, width=docx.shared.Inches(6))
                doc.add_paragraph(f"Screenshot {i+1}")

            buffer = BytesIO()
            doc.save(buffer)
            buffer.seek(0)

            st.download_button(
                label="Download Report with Screenshots",
                data=buffer,
                file_name=f"{url}_critique_with_screenshots.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

if __name__ == "__main__":
    main()
