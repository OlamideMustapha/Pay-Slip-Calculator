import pandas as pd
import numpy as np
import json
import datetime
import pyodbc
import sqlalchemy
from six.moves import urllib


## TODO:
## Comment code
## Write Pay slip to csv
## exception handling
## Optimize code base
## Document code base


tax_path      = "tax.json"
employee_path = "Employee.txt"
hours_path    = "Hours.txt"


tax_band           = 700 
default_tax_credit = 70

with open (tax_path, 'r') as f:
    # json.load
    tax = json.load (f)

employee_col_names = [
    "StaffID","Surname","FirstName(s)",
    "PPSNumber","StandardHours","HourlyRate",
    "OvertimeRate","TaxCredit","StandardBand"
]

hours_col_names = ["Date", "StaffID", "HoursWorked"]


employee_df = pd.read_csv (employee_path, delimiter="\t", names=employee_col_names)
hours_df    = pd.read_csv (hours_path, delimiter="\t", names=hours_col_names)


pay_slip_df = hours_df.merge (employee_df, on="StaffID")

pay_slip_df ['Date'] = pd.to_datetime (pay_slip_df ['Date'], format='%d/%m/%Y')


pay_slip_df ['NormalHours'] = np.where (
  pay_slip_df.HoursWorked >= pay_slip_df.StandardHours,
  pay_slip_df.StandardHours,
  pay_slip_df.HoursWorked)

pay_slip_df ['NormalAmount'] = pay_slip_df.NormalHours * pay_slip_df.HourlyRate


pay_slip_df ['OvertimeHours'] = np.where (
  pay_slip_df.HoursWorked <= pay_slip_df.StandardHours,
  pay_slip_df.HoursWorked,
  pay_slip_df.HoursWorked - pay_slip_df.StandardHours)

pay_slip_df ['OvertimeAmount']  = pay_slip_df.OvertimeHours * pay_slip_df.OvertimeRate


### Calculating employee gross pay
pay_slip_df ['GrossPay'] = pay_slip_df ["NormalAmount"] + pay_slip_df ["OvertimeAmount"]


### Calculating employee standard tax
pay_slip_df ['StandardTaxRate'] = float (tax['Standard Rate'])
pay_slip_df ['HigherTaxRate']   = float (tax['Higher Rate'])

pay_slip_df ['StandardBand'] = np.where (
  pay_slip_df.GrossPay <= pay_slip_df.StandardBand,
  pay_slip_df.GrossPay,
  pay_slip_df.StandardBand)

pay_slip_df ['StandardTax'] = pay_slip_df.StandardBand * (pay_slip_df.StandardTaxRate / 100)


pay_slip_df ['HigherBand'] = np.where (
  pay_slip_df.GrossPay <= pay_slip_df.StandardBand,
  0,
  pay_slip_df.GrossPay - pay_slip_df.StandardBand)

pay_slip_df ['HigherTax'] = pay_slip_df.HigherBand * (pay_slip_df.HigherTaxRate / 100)


pay_slip_df ['TotalDeductions'] = pay_slip_df ['StandardTax'] + pay_slip_df ["HigherTax"]

pay_slip_df ['TaxCredit'] = np.where (
  pay_slip_df.TaxCredit > pay_slip_df.TotalDeductions,
  pay_slip_df.TotalDeductions,
  pay_slip_df.TaxCredit
)

pay_slip_df ['NetDeductions'] = pay_slip_df ['TotalDeductions'] - pay_slip_df ['TaxCredit']
pay_slip_df ['NetPay'] = pay_slip_df ['GrossPay'] - pay_slip_df ['NetDeductions']


avg_gross_pay_per_week = pay_slip_df.groupby ('Date') ['GrossPay'] \
  .mean () \
  .to_frame ('AverageGrossPay')

cum_gross_pay = pay_slip_df [
  pay_slip_df ['Date'] + pd.DateOffset(weeks=6) < datetime.datetime.now() ] \
  .groupby ('StaffID') ['GrossPay'] \
  .sum () \
  .to_frame ('CumulativeGrossPay')

def pay_table (pay_slip):
  header   = "%-18s\t%8s\t%9s\t%8s\n"%("", "Hours", "Rate", "Total")
  regular  = "%-18s\t%8i\t%8i%%\t%8i\n"%("Regular", pay_slip.StandardHours, pay_slip.HourlyRate, pay_slip.NormalAmount)
  overtime = "%-18s\t%8i\t%8i%%\t%8i\n"%("Overtime", pay_slip.OvertimeHours, pay_slip.OvertimeRate, pay_slip.OvertimeAmount)
  gross    = "%-18s\t%8s\t%8s\t%8i\n"%("Gross Pay", "", "", pay_slip.GrossPay)

  return header + regular + overtime + gross + '\n'


def tax_table (pay_slip):
  header   = "%-18s\t%8s\t%9s\t%8s\n"%("", "Amount", "Rate", "Total")
  standard = "%-18s\t%8i\t%8i%%\t%8i\n"%("Standard Rate", pay_slip.StandardBand, pay_slip.StandardTaxRate, pay_slip.StandardTax)
  higher   = "%-18s\t%8i\t%8i%%\t%8i\n"%("Higher Rate", pay_slip.HigherBand, pay_slip.HigherTaxRate, pay_slip.HigherTax)
  
  total_dedu = "%-18s\t%8s\t%8s\t%8i\n"%("Total Deductions", "", "", pay_slip.TotalDeductions)
  tax_credit = "%-18s\t%8s\t%8s\t%8i\n"%("Tax Credit", "", "", pay_slip.TaxCredit)
  net_deduc  = "%-18s\t%8s\t%8s\t%8i\n"%("Net Deductions", "", "", pay_slip.NetDeductions)
  net_pay    = "%-18s\t%8s\t%8s\t%8i\n"%("Net Pay", "", "", pay_slip.NetPay)

  return header + standard + higher + '\n' + total_dedu + tax_credit + net_deduc + net_pay

def generate_file_name (pay_slip) -> str:
  """Generate the file name to save payslip
  Args:
      # payment_info (dict): Employee informations as a dictionary
  Returns:
      [str]: file name
  """

  date = str (pay_slip ['Date']).replace ('-', '').split (' ')

  return str (pay_slip ['StaffID']) + date [0]

def write_pay_slip (pay_slip):
  info = f"""StaffID: {pay_slip.StaffID}
Staff Name: {pay_slip.Surname + ' ' + pay_slip ["FirstName(s)"]}
PPSN: {pay_slip.PPSNumber}
Date: {pay_slip.Date}

"""
  pay_ = pay_table (pay_slip)
  tax_ = tax_table (pay_slip)

  name = generate_file_name (pay_slip)
  with open (f'./pay_slips/{name}.txt', 'w') as f:
    f.write (info + pay_ + tax_)


pay_slip_df.apply (write_pay_slip, axis=1)

# print (avg_gross_pay_per_week)
# print (cum_gross_pay)

# params = urllib.parse.quote_plus("DRIVER={ODBC Driver 17 for SQL Server};SERVER=52.151.85.62;DATABASE=B9DA100_DB;UID=sa;PWD=passwords")
# engine = sqlalchemy.create_engine("mssql+pyodbc:///?odbc_connect=%s" % params)
# engine.connect() 

# pay_slip_df.to_sql(name='PaySlip',con=engine, index=False, if_exists='append')