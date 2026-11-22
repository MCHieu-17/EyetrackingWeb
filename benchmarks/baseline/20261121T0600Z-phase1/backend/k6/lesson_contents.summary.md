# k6 summary

scenario: lesson_contents

- iterations: count=235.000, rate=23.153
- http_req_duration{expected_response:true}: p(99)=34.485, avg=15.153, min=6.373, med=13.022, max=36.098, p(90)=23.729, p(95)=24.556
- http_req_waiting: avg=15.015, min=6.308, med=12.697, max=36.015, p(90)=23.334, p(95)=24.450, p(99)=34.265
- http_req_failed: rate=0.000
- http_req_connecting: med=0.000, max=0.882, p(90)=0.000, p(95)=0.000, p(99)=0.752, avg=0.016, min=0.000
- http_req_sending: p(90)=0.047, p(95)=0.056, p(99)=0.113, avg=0.028, min=0.005, med=0.024, max=0.123
- http_req_receiving: max=0.711, p(90)=0.246, p(95)=0.342, p(99)=0.455, avg=0.110, min=0.023, med=0.074
- http_req_blocked: min=0.001, med=0.007, max=0.953, p(90)=0.012, p(95)=0.014, p(99)=0.801, avg=0.024
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_duration: min=6.373, med=13.022, max=36.098, p(90)=23.729, p(95)=24.556, p(99)=34.485, avg=15.153
- vus: min=5.000, max=5.000
