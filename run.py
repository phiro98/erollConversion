from flask import Flask, request, send_file, render_template_string
import pandas as pd
import os
import cv2
import numpy as np
import pdf2image
import pytesseract
import csv


# Function to ensure the output directory exists
def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string(open("index.html").read())

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file uploaded", 400

    file = request.files['file']
    temp_filename = "temp_file.pdf"
    file.save(temp_filename)
    print(temp_filename)
    # Extract pages from PDF in proper quality
    pages = pdf2image.convert_from_path(temp_filename, first_page=3, last_page=30, dpi=300, grayscale=True)
    counter = 3
    # Define the output directory based on PDF name
    pdf_name = temp_filename #'abcd.pdf'
    base_name = os.path.splitext(pdf_name)[0]
    output_dir = base_name

    # Ensure the output directory exists
    ensure_dir(output_dir)

    # Define the output text file path
    csv_file_path = os.path.join(output_dir, f'{output_dir}.csv')

    # Open the output text file for writing
    with open(csv_file_path, 'w', newline='', encoding='utf-8') as csv_file:
        csv_writer = csv.writer(csv_file)

        for page in pages:
            print(f"page_{counter}:::")

            page_np = np.array(page)
            # Inverse binarize for contour finding
            thr = cv2.threshold(page_np, 128, 255, cv2.THRESH_BINARY_INV)[1]

            # Find contours w.r.t. the OpenCV version
            cnts = cv2.findContours(thr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            cnts = cnts[0] if len(cnts) == 2 else cnts[1]


            # Mask out the two tables
            cnts_tables = [cnt for cnt in cnts if cv2.contourArea(cnt) > 10000]
            no_tables = cv2.drawContours(thr.copy(), cnts_tables, -1, 0, cv2.FILLED)

            # Find bounding rectangles of texts outside of the two tables
            no_tables = cv2.morphologyEx(no_tables, cv2.MORPH_CLOSE, np.full((21, 51), 255))
            cnts = cv2.findContours(no_tables, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            cnts = cnts[0] if len(cnts) == 2 else cnts[1]
            rects = sorted([cv2.boundingRect(cnt) for cnt in cnts], key=lambda r: (r[1], r[0]))  # Sort by y first, then x

            # Extract texts from each bounding rectangle
            csv_writer.writerow(['Extract texts outside of the two tables'])
            print('\nExtract texts outside of the two tables\n')
            for (x, y, w, h) in rects:
                text_dn = pytesseract.image_to_string(page_np[y:y+h, x:x+w], config='--psm 6', lang='Devanagari')
                text_dn = text_dn.replace('\f', ' ').replace(',', ";")
                csv_writer.writerow([text_dn])
            csv_writer.writerow(['Voter ID', 'Name', 'Guardian Name', 'House Number','Picture Availibility', 'Age', 'Gender'])

            # STEP 2: Extract texts from inside of the two tables
            rects = sorted([cv2.boundingRect(cnt) for cnt in cnts_tables], key=lambda r: (r[1], r[0]))  # Sort by y first, then x

            # Iterate each table
            for i_r, (x, y, w, h) in enumerate(rects, start=1):

                # Find bounding rectangles of cells inside of the current table
                cnts = cv2.findContours(page_np[y+2:y+h-2, x+2:x+w-2], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
                cnts = cnts[0] if len(cnts) == 2 else cnts[1]
                inner_rects = sorted([cv2.boundingRect(cnt) for cnt in cnts], key=lambda r: (r[1], r[0]))  # Sort by y first, then x


                # Extract texts from each cell of the current table
                # csv_writer.writerow([f'Extract texts inside table {i_r}'])
                print(f'\nExtract texts inside table {i_r}\n')
                for (xx, yy, ww, hh) in inner_rects:
                    try:
                        # Set current coordinates w.r.t. full image
                        xx += x
                        yy += y
                        
                        # Get current cell
                        cell = page_np[yy:yy+hh, xx:xx+ww]
                        text = pytesseract.image_to_string(cell, config='--psm 6', lang='Devanagari+eng')
                        print(text)
                        text = text.replace('\f', ' ')#.replace('\n', ' ')
                        
                        text_lines = text.split('\n')
                        clean_text = [string for string in text_lines if string.strip()]
                        if len(clean_text) == 5:
                            print(clean_text)
                            pictute_availibility = True if clean_text[3].split()[-1] == 'उपलब्ध' else False
                            gaurdian_name = clean_text[2].split('नामः')[1].strip() if 'नामः' in clean_text[2] else clean_text[2].split(':')[1].strip()
                            
                            row = {
                                "voterID":clean_text[0].split()[-1],
                                "name":clean_text[1].split(':')[1].strip(),
                                "gaurdian_name":gaurdian_name,
                                "house_no":clean_text[3].split(':')[1].split()[0].strip(),
                                "picture_availibility": pictute_availibility,
                                "age":clean_text[4].split(':')[1].split()[0],
                                "gender": clean_text[4].strip().split()[-1]

                            }
                            print(row)
                            csv_writer.writerow(row.values())
                        elif len(clean_text) == 4:
                            i=0
                            print(clean_text)
                            pictute_availibility = True if clean_text[3].split()[-1] == 'उपलब्ध' else False
                            gaurdian_name = clean_text[i+1].split('नामः')[1].strip() if 'नामः' in clean_text[i+1] else clean_text[i+1].split(':')[1].strip()
                            row = {
                                "voterID":'',
                                "name":clean_text[i].split(':')[1].strip(),
                                "gaurdian_name":gaurdian_name,
                                "house_no":clean_text[i+2].split(':')[1].split()[0].strip(),
                                "picture_availibility": pictute_availibility,
                                "age":clean_text[i+3].split(':')[1].split()[0],
                                "gender": clean_text[i+3].strip().split()[-1]

                            }
                            print(row)
                            csv_writer.writerow(row.values())
                    except:
                        continue
            counter += 1

    return send_file(csv_file_path, as_attachment=True)

    os.remove(temp_filename)
    os.remove(csv_file_path)

if __name__ == '__main__':
    app.run(debug=True)
