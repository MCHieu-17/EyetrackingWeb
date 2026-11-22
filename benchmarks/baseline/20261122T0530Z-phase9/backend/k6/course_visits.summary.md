# k6 summary

scenario: course_visits

- vus: min=5.000, max=5.000
- http_req_duration: med=9.551, max=27.544, p(90)=18.735, p(95)=19.233, p(99)=25.102, avg=11.411, min=3.006
- http_req_connecting: avg=0.002, min=0.000, med=0.000, max=0.110, p(90)=0.000, p(95)=0.000, p(99)=0.101
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_duration{expected_response:true}: p(90)=18.735, p(95)=19.233, p(99)=25.102, avg=11.411, min=3.006, med=9.551, max=27.544
- iterations: count=238.000, rate=23.514
- http_req_sending: p(99)=0.081, avg=0.040, min=0.004, med=0.041, max=0.147, p(90)=0.052, p(95)=0.058
- http_req_receiving: p(90)=0.429, p(95)=0.500, p(99)=1.027, avg=0.213, min=0.035, med=0.127, max=3.105
- http_req_blocked: min=0.001, med=0.011, max=0.144, p(90)=0.014, p(95)=0.015, p(99)=0.123, avg=0.013
- http_req_waiting: avg=11.158, min=2.930, med=9.346, max=27.440, p(90)=18.438, p(95)=18.826, p(99)=24.890
- http_req_failed: rate=0.000
