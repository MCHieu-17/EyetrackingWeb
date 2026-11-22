# k6 summary

scenario: session_contents

- http_req_blocked: max=0.125, p(90)=0.014, p(95)=0.018, p(99)=0.124, avg=0.013, min=0.002, med=0.011
- http_req_duration: avg=14.556, min=3.780, med=15.507, max=26.665, p(90)=21.464, p(95)=22.135, p(99)=26.273
- http_req_duration{expected_response:true}: p(99)=26.273, avg=14.556, min=3.780, med=15.507, max=26.665, p(90)=21.464, p(95)=22.135
- http_req_receiving: min=0.017, med=0.077, max=0.408, p(90)=0.219, p(95)=0.266, p(99)=0.385, avg=0.106
- vus: min=5.000, max=5.000
- http_req_sending: p(99)=0.077, avg=0.039, min=0.006, med=0.040, max=0.095, p(90)=0.055, p(95)=0.058
- http_req_failed: rate=0.000
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.088, avg=0.002, min=0.000, med=0.000, max=0.089
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- iterations: count=233.000, rate=23.203
- http_req_waiting: p(99)=26.169, avg=14.411, min=3.727, med=15.301, max=26.481, p(90)=21.254, p(95)=22.022
