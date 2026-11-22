# k6 summary

scenario: course_visits

- http_req_blocked: p(95)=0.015, p(99)=0.126, avg=0.013, min=0.002, med=0.011, max=0.141, p(90)=0.013
- http_req_receiving: p(99)=3.053, avg=0.285, min=0.035, med=0.167, max=3.762, p(90)=0.412, p(95)=0.617
- http_req_failed: rate=0.000
- http_req_waiting: p(99)=66.343, avg=13.359, min=3.111, med=12.842, max=73.600, p(90)=18.457, p(95)=19.308
- iterations: count=235.000, rate=23.112
- http_req_duration{expected_response:true}: p(90)=18.722, p(95)=19.693, p(99)=66.666, avg=13.688, min=3.220, med=13.184, max=73.709
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_connecting: p(99)=0.103, avg=0.002, min=0.000, med=0.000, max=0.106, p(90)=0.000, p(95)=0.000
- http_req_duration: max=73.709, p(90)=18.722, p(95)=19.693, p(99)=66.666, avg=13.688, min=3.220, med=13.184
- vus: min=5.000, max=5.000
- http_req_sending: p(90)=0.049, p(95)=0.056, p(99)=0.136, avg=0.044, min=0.011, med=0.040, max=0.675
