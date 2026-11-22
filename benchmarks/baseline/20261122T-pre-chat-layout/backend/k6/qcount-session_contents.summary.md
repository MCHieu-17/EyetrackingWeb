# k6 summary

scenario: session_contents

- http_req_receiving: med=0.124, max=0.322, p(90)=0.218, p(95)=0.272, p(99)=0.312, avg=0.132, min=0.029
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_failed: rate=0.000
- http_req_blocked: p(95)=0.048, p(99)=0.125, avg=0.020, min=0.004, med=0.011, max=0.144, p(90)=0.023
- vus: min=1.000, max=1.000
- iterations: rate=4.710, count=20.000
- http_req_connecting: min=0.000, med=0.000, max=0.107, p(90)=0.000, p(95)=0.005, p(99)=0.087, avg=0.005
- http_req_duration: p(99)=14.949, avg=11.195, min=2.871, med=12.735, max=14.962, p(90)=14.375, p(95)=14.901
- http_req_sending: max=0.060, p(90)=0.052, p(95)=0.056, p(99)=0.059, avg=0.043, min=0.013, med=0.043
- http_req_waiting: p(90)=14.164, p(95)=14.699, p(99)=14.719, avg=11.019, min=2.824, med=12.553, max=14.724
- http_req_duration{expected_response:true}: max=14.962, p(90)=14.375, p(95)=14.901, p(99)=14.949, avg=11.195, min=2.871, med=12.735
