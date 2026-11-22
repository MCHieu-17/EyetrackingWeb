# k6 summary

scenario: session_contents

- iterations: count=20.000, rate=4.667
- http_req_waiting: med=15.833, max=18.038, p(90)=17.055, p(95)=17.863, p(99)=18.003, avg=12.940, min=3.895
- http_req_blocked: p(90)=0.014, p(95)=0.022, p(99)=0.126, avg=0.018, min=0.003, med=0.011, max=0.152
- http_req_sending: min=0.013, med=0.045, max=0.074, p(90)=0.062, p(95)=0.074, p(99)=0.074, avg=0.048
- vus: max=1.000, min=1.000
- http_req_failed: rate=0.000
- http_req_duration: avg=13.099, min=3.941, med=16.028, max=18.176, p(90)=17.273, p(95)=18.132, p(99)=18.167
- http_req_connecting: med=0.000, max=0.103, p(90)=0.000, p(95)=0.005, p(99)=0.083, avg=0.005, min=0.000
- http_req_duration{expected_response:true}: min=3.941, med=16.028, max=18.176, p(90)=17.273, p(95)=18.132, p(99)=18.167, avg=13.099
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_receiving: avg=0.112, min=0.031, med=0.106, max=0.281, p(90)=0.175, p(95)=0.228, p(99)=0.270
