import smtplib 
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class SMS(object):

	def __init__(self, email, password):

		self.email = email
		self.password = password
		self.smtp = "smtp.gmail.com" 
		self.port = 587
		self.server = smtplib.SMTP(self.smtp, self.port)
		self.server.starttls()
		self.server.login(self.email, self.password)
		self.gateways = ['txt.att.net', '@tmomail.net', 'vtext.com', 'pm.sprint.com']

	def send_message(self, number, message):
		m = MIMEMultipart()
		m['From'] = self.email
		m.attach(MIMEText(message, 'plain'))
		sms = m.as_string()
		for gate in self.gateways:
			gateway = f'{number}@{gate}'
			m['To'] = gateway
			try:
				self.server.sendmail(self.email, gateway, sms)
			except Exception as E:
				print(E)
		return 

	def send_messages(self, numbers, message):
		for number in numbers:
			self.send_message(number, message)
		return 

	def close(self):
		self.server.quit()
