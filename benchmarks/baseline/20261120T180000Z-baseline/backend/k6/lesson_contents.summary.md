# k6 summary

scenario: lesson_contents

- vus: min=5.000, max=5.000
- http_req_waiting: avg=18.415, min=7.045, med=16.622, max=41.884, p(90)=29.022, p(95)=34.241, p(99)=40.681
- http_req_connecting: max=1.053, p(90)=0.000, p(95)=0.000, p(99)=0.927, avg=0.020, min=0.000, med=0.000
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_receiving: avg=0.119, min=0.028, med=0.082, max=1.097, p(90)=0.238, p(95)=0.281, p(99)=0.436
- http_req_failed: rate=0.000
- http_req_blocked: max=1.120, p(90)=0.013, p(95)=0.016, p(99)=0.994, avg=0.033, min=0.002, med=0.011
- http_req_sending: p(99)=0.156, avg=0.043, min=0.004, med=0.040, max=0.471, p(90)=0.058, p(95)=0.075
- iterations: count=230.000, rate=22.783
- http_req_duration: med=16.799, max=42.023, p(90)=29.124, p(95)=34.494, p(99)=40.841, avg=18.576, min=7.300
- http_req_duration{expected_response:true}: med=16.799, max=42.023, p(90)=29.124, p(95)=34.494, p(99)=40.841, avg=18.576, min=7.300
