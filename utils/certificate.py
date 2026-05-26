import os
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from datetime import datetime

def generate_certificate(student_name, course_name, cert_id):
    """Generates a simple PDF certificate."""
    certificates_dir = 'certificates'
    if not os.path.exists(certificates_dir):
        os.makedirs(certificates_dir)
        
    filename = f"{cert_id}.pdf"
    filepath = os.path.join(certificates_dir, filename)
    
    # Setup canvas
    c = canvas.Canvas(filepath, pagesize=landscape(letter))
    width, height = landscape(letter)
    
    # Draw border
    c.setStrokeColor(colors.HexColor('#1E3A8A')) # Blue
    c.setLineWidth(10)
    c.rect(0.5*inch, 0.5*inch, width - 1.0*inch, height - 1.0*inch)
    
    # Title
    c.setFont("Helvetica-Bold", 36)
    c.setFillColor(colors.HexColor('#1E3A8A'))
    c.drawCentredString(width/2.0, height - 2.0*inch, "Certificate of Completion")
    
    # Subtitle
    c.setFont("Helvetica", 18)
    c.setFillColor(colors.black)
    c.drawCentredString(width/2.0, height - 3.0*inch, "This is to certify that")
    
    # Student Name
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(colors.HexColor('#2563EB'))
    c.drawCentredString(width/2.0, height - 4.0*inch, student_name)
    
    # Course info
    c.setFont("Helvetica", 16)
    c.setFillColor(colors.black)
    c.drawCentredString(width/2.0, height - 5.0*inch, "has successfully completed the course")
    
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(colors.HexColor('#1E3A8A'))
    c.drawCentredString(width/2.0, height - 6.0*inch, course_name)
    
    # Date and ID
    issue_date = datetime.now().strftime("%B %d, %Y")
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.gray)
    c.drawCentredString(width/2.0, height - 7.0*inch, f"Issued on: {issue_date} | Certificate ID: {cert_id}")
    
    c.save()
    return filename
