# k6 summary

scenario: course_visits

- http_req_receiving: med=0.112, max=2.015, p(90)=0.271, p(95)=0.323, p(99)=1.228, avg=0.173, min=0.033
- http_req_blocked: p(95)=0.015, p(99)=0.093, avg=0.010, min=0.002, med=0.009, max=0.111, p(90)=0.013
- http_req_duration: min=15.034, med=28.043, max=68.911, p(90)=43.062, p(95)=57.146, p(99)=66.672, avg=30.832
- vus: min=5.000, max=5.000
- http_req_failed: rate=0.000
- http_req_sending: max=0.200, p(90)=0.047, p(95)=0.052, p(99)=0.073, avg=0.029, min=0.004, med=0.030
- http_req_waiting: med=27.807, max=68.836, p(90)=42.951, p(95)=57.028, p(99)=66.455, avg=30.631, min=14.925
- http_req_connecting: min=0.000, med=0.000, max=0.081, p(90)=0.000, p(95)=0.000, p(99)=0.068, avg=0.002
- iterations: count=220.000, rate=21.580
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_duration{expected_response:true}: p(99)=66.672, avg=30.832, min=15.034, med=28.043, max=68.911, p(90)=43.062, p(95)=57.146
