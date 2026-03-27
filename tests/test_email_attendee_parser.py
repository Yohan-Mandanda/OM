import unittest

from email_attendee_parser import parse_email_content, should_skip_email


EX1_TABLE_TEMPLATE = """
<html>
  <body>
    <h2>Attendees for 1BX65896 have been now updated by Admin.</h2>
    <table>
      <tr><td>Order ID:</td><td>1BX65896</td></tr>
      <tr><td>Event:</td><td>AC Milan vs Torino</td></tr>
    </table>
    <h3>Attendee information</h3>
    <table>
      <thead>
        <tr>
          <th>First Name</th>
          <th>Last Name</th>
          <th>Email</th>
          <th>Nationality</th>
          <th>Date Of Birth</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Elena</td>
          <td>Riboldi</td>
          <td></td>
          <td>Italy</td>
          <td>29-Dec-1984</td>
        </tr>
      </tbody>
    </table>
    <p>Thank you for using SeatsBrokers.com</p>
  </body>
</html>
"""

EX2_LABELED_NUMBERED = """
<html>
  <body>
    <p>Hello team,</p>
    <p>
      Attached to this email are the details for two attendees for order
      <b>4899272</b>.
    </p>
    <ul>
      <li><b>Full name 1: Balint Csere</b></li>
      <li><b>Date of Birth (dd/mm/yyyy): 02/09/1976</b></li>
      <li><b>Gender: Male</b></li>
      <li><b>City of Birth: Budapest</b></li>
      <li><b>Province of City of Birth: Budapest</b></li>
      <li><b>Nationality: Hungarian</b></li>
    </ul>
    <ul>
      <li><b>Full name 2: Krisztina Budavari</b></li>
      <li><b>Date of Birth (dd/mm/yyyy): 28/04/1978</b></li>
      <li><b>Gender: Female</b></li>
      <li><b>City of Birth: Budapest</b></li>
      <li><b>Province of City of Birth: Budapest</b></li>
      <li><b>Nationality: Hungarian</b></li>
    </ul>
    <p>Kind Regards, Fulfillment Team</p>
  </body>
</html>
"""

EX3_ATTENDEE_HEADERS = """
<html>
  <body>
    <h1>viagogo customer support update Order - 633127305</h1>
    <p>Please find below the email addresses and FAN IDs provided by your buyer.</p>
    <div>Attendee 1:</div>
    <div>Name: Hicham Hugo Yvain</div>
    <div>Fan ID: 25MARAN19980731M0003</div>
    <div>E-mail: yvain.hicham@hotmail.fr</div>
    <div>Phone Number: 33620844368</div>
    <br />
    <div>Attendee 2:</div>
    <div>Name: Thierry Nicolas Yvain</div>
    <div>Fan ID: 25FRAAN19631117M0002</div>
    <div>E-mail: rokia.yvain@orange.fr</div>
    <div>Phone Number: 33670649165</div>
    <p>Please don't reply directly to this message.</p>
  </body>
</html>
"""

EX4_TRIPLETS = """
<html>
  <body>
    <p>
      The customer for order <strong>#77762534</strong> has provided the following details.
    </p>
    <p>
      Oleg Brennan<br />
      2/3/2005<br />
      American<br /><br />
      Beatriz Polo Diz<br />
      11/15/2005<br />
      Brazilian with Italian Passport
    </p>
    <table border="1">
      <tr><td>Event:</td><td>AC Milan vs Torino FC</td></tr>
      <tr><td>Venue:</td><td>San Siro - Milan</td></tr>
    </table>
  </body>
</html>
"""

NO_ATTENDEE = """
<html>
  <body>
    <h1>Order update</h1>
    <p>Order ID: 12345678</p>
    <p>Event: AC Milan vs Torino</p>
    <p>Venue: San Siro</p>
    <p>Please do not reply to this message.</p>
  </body>
</html>
"""


class EmailAttendeeParserTests(unittest.TestCase):
    def test_extracts_table_attendee_info(self) -> None:
        result = parse_email_content(EX1_TABLE_TEMPLATE)
        self.assertEqual(result["order_id"], "1BX65896")
        self.assertFalse(result["should_skip"])
        self.assertEqual(len(result["attendee_blocks"]), 1)
        block = result["attendee_blocks"][0]
        self.assertIn("First Name: Elena", block)
        self.assertIn("Last Name: Riboldi", block)
        self.assertIn("Nationality: Italy", block)
        self.assertIn("Date Of Birth: 29-Dec-1984", block)
        self.assertNotIn("seatsbrokers", block.lower())

    def test_extracts_numbered_labeled_attendees(self) -> None:
        result = parse_email_content(EX2_LABELED_NUMBERED)
        self.assertEqual(result["order_id"], "4899272")
        self.assertFalse(result["should_skip"])
        self.assertEqual(len(result["attendee_blocks"]), 2)
        self.assertIn("Full Name: Balint Csere", result["attendee_blocks"][0])
        self.assertIn("Full Name: Krisztina Budavari", result["attendee_blocks"][1])

    def test_extracts_explicit_attendee_header_blocks(self) -> None:
        result = parse_email_content(EX3_ATTENDEE_HEADERS)
        self.assertEqual(result["order_id"], "633127305")
        self.assertFalse(result["should_skip"])
        self.assertEqual(len(result["attendee_blocks"]), 2)
        self.assertIn("Fan ID: 25MARAN19980731M0003", result["attendee_blocks"][0])
        self.assertIn("Email: rokia.yvain@orange.fr", result["attendee_blocks"][1])

    def test_extracts_unlabeled_triplets(self) -> None:
        result = parse_email_content(EX4_TRIPLETS)
        self.assertEqual(result["order_id"], "77762534")
        self.assertFalse(result["should_skip"])
        self.assertEqual(len(result["attendee_blocks"]), 2)
        self.assertIn("Full Name: Oleg Brennan", result["attendee_blocks"][0])
        self.assertIn("Nationality: Brazilian with Italian Passport", result["attendee_blocks"][1])

    def test_skip_when_no_attendee_detected(self) -> None:
        result = parse_email_content(NO_ATTENDEE)
        self.assertEqual(result["order_id"], "12345678")
        self.assertEqual(result["attendee_blocks"], [])
        self.assertTrue(result["should_skip"])
        self.assertTrue(should_skip_email(NO_ATTENDEE))

    def test_nested_table_header_noise_does_not_create_fake_attendees(self) -> None:
        html = """
        <html>
          <body>
            <table>
              <tbody>
                <tr>
                  <td>
                    <table>
                      <thead>
                        <tr>
                          <th>First Name</th>
                          <th>Last Name</th>
                          <th>Email</th>
                          <th>Nationality</th>
                          <th>Date Of Birth</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>Elena</td>
                          <td>Riboldi</td>
                          <td></td>
                          <td>Italy</td>
                          <td>29-Dec-1984</td>
                        </tr>
                      </tbody>
                    </table>
                  </td>
                </tr>
              </tbody>
            </table>
          </body>
        </html>
        """
        result = parse_email_content(html)
        self.assertEqual(len(result["attendee_blocks"]), 1)
        block = result["attendee_blocks"][0]
        self.assertIn("First Name: Elena", block)
        self.assertIn("Last Name: Riboldi", block)
        self.assertIn("Nationality: Italy", block)
        self.assertIn("Date Of Birth: 29-Dec-1984", block)
        self.assertNotIn("First Name: Last Name", result["attendee_raw_text"])


if __name__ == "__main__":
    unittest.main()
