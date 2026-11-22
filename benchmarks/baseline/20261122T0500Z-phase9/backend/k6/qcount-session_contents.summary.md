# k6 summary

scenario: session_contents

- http_req_duration{expected_response:true}: p(90)=14.877, p(95)=14.972, p(99)=15.027, avg=12.093, min=3.209, med=13.611, max=15.041
- http_req_blocked: p(99)=0.090, avg=0.017, min=0.003, med=0.012, max=0.107, p(90)=0.018, p(95)=0.024
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- iterations: count=20.000, rate=4.694
- http_req_duration: max=15.041, p(90)=14.877, p(95)=14.972, p(99)=15.027, avg=12.093, min=3.209, med=13.611
- http_req_sending: min=0.024, med=0.043, max=0.062, p(90)=0.050, p(95)=0.055, p(99)=0.061, avg=0.044
- http_req_failed: rate=0.000
- http_req_connecting: p(99)=0.062, avg=0.004, min=0.000, med=0.000, max=0.077, p(90)=0.000, p(95)=0.004
- vus: min=1.000, max=1.000
- http_req_waiting: med=13.425, max=14.892, p(90)=14.705, p(95)=14.818, p(99)=14.877, avg=11.922, min=3.106
- http_req_receiving: p(90)=0.159, p(95)=0.175, p(99)=0.370, avg=0.127, min=0.040, med=0.115, max=0.418
